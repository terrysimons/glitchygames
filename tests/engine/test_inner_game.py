"""A game's own command replayed inside its own engine context (glitchygames/inner_game.py).

``InnerGame.replay`` calls an installed command's entry point, unchanged, in a fresh engine
context with a render target and a private event queue; the host steps its frames one at a time
and reads how it ended from ``InnerGame.outcome`` (plans/2026-11-12-arcade-3-inner-game.md, Task
3). The game is a stand-in installed as a command (tests/stand_in_games.py), recorded once in a
child process; the inner game imports its package through the command's entry point, as an
installed console script would.

The plan's Review Focus is tested here: a recorded quit ends only its inner game (1), a
divergence ends it with the report and writes nothing to stdout (2), and a game that raises or
exits while building or stepping fails alone, the default context current afterwards (3).
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import TYPE_CHECKING, Protocol

import pygame
import pytest

from glitchygames import events
from glitchygames.audio import voices
from glitchygames.audio.engine import AUDIO_ENGINE_SLOT
from glitchygames.audio.instrument import Instrument
from glitchygames.audio.live import LiveAudio
from glitchygames.audio.live_instrument import LiveSoundHandle
from glitchygames.audio.route import is_audible
from glitchygames.audio.voices import (
    INNER_CHANNELS_SLOT,
    ChannelPartition,
    InnerGameChannelsError,
    heard_set_start,
    release_channels,
    reserve_channels,
    reserve_inner_game_channels,
    reserved_channel_count,
)
from glitchygames.engine import GameEngine
from glitchygames.engine.game_engine import CURRENT_ENGINE_SLOT
from glitchygames.engine_context import current_context, default_context
from glitchygames.feature_flags import flag_state
from glitchygames.inner_game import (
    FLAG_VALUE_COUNTS,
    REFUSED_FLAGS,
    REFUSED_SHORT_FLAG_LETTERS,
    SHORT_FLAGS_TAKING_A_VALUE,
    InnerGame,
    InnerGameAudibleError,
    InnerGameOutcome,
    InnerGameRefusedError,
    InnerGameState,
    InnerGameStateError,
    engine_option_actions,
    inherited_arguments,
    is_refused_argument,
    is_refused_short_flag_cluster,
    refused_arguments,
)
from glitchygames.render_target import render_target
from glitchygames.replay.input_blocking import REAL_INPUT_EVENT_TYPES
from glitchygames.replay.pacer import TickBudget
from glitchygames.replay.tools.golden_traces import GoldenTraceEngine
from glitchygames.scenes import Scene, SceneManager
from glitchygames.sprites.spawned import SpawnedSprite
from tests import demo_runs
from tests.audio.voice_support import (
    LEGACY_CHANNELS,
    LIBRARY_CHANNELS,
    LIVE_POOL,
    SAMPLE_RATE,
    unreserved_channel_ids,
)
from tests.inner_game_tiles import (
    Tile,
    assert_no_tile_is_heard,
    play_alone,
    reference_digests,
)
from tests.replay.replay_helpers import rewrite_recording, tamper_first_sprite_rect
from tests.stand_in_games import (
    STAND_IN_GAME_RESOLUTION,
    STAND_IN_SPAWN_POINT,
    StandInGame,
    copy_recording,
    record_stand_in_game_once,
    use_stand_in_game,
    write_chiming_stand_in_game,
    write_live_voice_stand_in_game,
    write_spawning_stand_in_game,
    write_stand_in_distribution,
    write_stand_in_game,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from pathlib import Path
    from typing import Any

    from pytest_mock import MockerFixture

# The stand-in's package: a name no other test's stand-in uses, since this process imports it
STAND_IN_PACKAGE = 'inner_game_rally'
# The chiming stand-in's package (a plain Sound.play() on CHIME_FRAME) and that frame
CHIMING_STAND_IN_PACKAGE = 'inner_game_chime'
CHIME_FRAME = 3
# The spawning stand-in's package (a /sprite spawn posted on SPAWN_FRAME) and that frame
SPAWNING_STAND_IN_PACKAGE = 'inner_game_spawner'
SPAWN_FRAME = 3
# The live-voice stand-in's package (a live synth voice from LIVE_VOICE_FRAME on) and that frame
LIVE_VOICE_STAND_IN_PACKAGE = 'inner_game_projector'
LIVE_VOICE_FRAME = 2
# The channel sizes a recording asks for (--sound-channels, --live-voice-pool), not the defaults
SMALL_CHANNELS_STAND_IN_PACKAGE = 'inner_game_small_channels'
SMALL_LIBRARY_CHANNELS = 6
SMALL_LIVE_POOL = 2
# A recording asking for more library channels than a heard set holds (32): it replays silent
TOO_BIG_STAND_IN_PACKAGE = 'inner_game_too_big'
TOO_BIG_LIBRARY_CHANNELS = 33
# A recording asking for a larger live pool than declared per inner game (4): it fails alone
BIG_POOL_STAND_IN_PACKAGE = 'inner_game_big_pool'
BIG_LIVE_POOL = 5
# The inner games every test may build at once (reserve_inner_game_channels, the host's call)
DECLARED_INNER_GAMES = 3
# The outer game's own sound: long enough to outlast every step a test runs
OUTER_SOUND_SECONDS = 8
# Bytes per second of the harness's mixer (signed 16-bit, stereo)
MIXER_BYTES_PER_SECOND = SAMPLE_RATE * 2 * 2
# A command whose entry point returns without starting an engine
COMMAND_THAT_STARTS_NOTHING = 'inner-game-starts-nothing'
COMMAND_THAT_STARTS_NOTHING_PACKAGE = 'inner_game_starts_nothing'
# The render target: the recording's screen size (a replay opens at its recorded size)
TARGET_SIZE = (
    int(STAND_IN_GAME_RESOLUTION.split('x')[0]),
    int(STAND_IN_GAME_RESOLUTION.split('x')[1]),
)
# A size the recording was not made at: the replay refuses it (rule 1 of replay/driver.py)
ANOTHER_SIZE = (TARGET_SIZE[0] + 16, TARGET_SIZE[1])
# The frame a tampered copy first differs at
TAMPERED_FRAME = 10
# A fast-forward's budgets run on a fake clock on which each frame costs this (frame_cost_clock):
# a power of two, so every multiple and difference of multiples is exact in a float and a k-frame
# budget is spent by exactly k frames (0.004 is not: from frame 9 one frame left it unspent)
FRAME_COST_SECONDS = 1 / 256
# The start frames and budgets (in frames) the frame-cost clock is checked over: longer than any
# recording a test fast-forwards
FRAME_COST_CHECKED_START_FRAMES = 5000
FRAME_COST_CHECKED_BUDGET_FRAMES = (1, 2, 3, 5, 8)
# The frame the sliced fast-forwards go to, and the frames a slice allows: not a multiple of it
SLICED_TO_FRAME = 10
FRAMES_PER_SLICE = 3
# More steps than any stand-in recording holds: a loop that never ends fails instead of hanging
MOST_STEPS = 500
# Quiet inner engines: their INFO lines would only crowd a failing test's output
QUIET = ('--log-level', 'error')
# SDL's driver variables, which an inner game never changes
SDL_DRIVER_VARIABLES = ('SDL_VIDEODRIVER', 'SDL_AUDIODRIVER')
# A user event the tests leave in SDL's queue: an inner game must neither take it nor add to it
SENTINEL_EVENT_TYPE = pygame.USEREVENT + 7
# An outer game's blocked event types other than the engine's own (every type allowed but
# SYSWMEVENT): an inner engine allowing every type, or a manager allowing its own, would show
OUTER_BLOCKED_TYPES = (*events.CONTROLLER_EVENTS, pygame.MOUSEWHEEL)
OUTER_ALLOWED_TYPES = (pygame.SYSWMEVENT,)


@pytest.fixture(scope='module')
def recorded_stand_in(tmp_path_factory: pytest.TempPathFactory) -> tuple[StandInGame, Path]:
    """Record the stand-in game once per module (and xdist worker).

    Returns:
        The stand-in game and its recording (each test copies it before reading it).

    """
    root = tmp_path_factory.mktemp('inner-game')
    game = write_stand_in_game(directory=root / 'site-packages', package=STAND_IN_PACKAGE)
    recording = record_stand_in_game_once(game=game, path=root / 'recorded.jsonl.gz')
    return game, recording


@pytest.fixture
def stand_in(
    recorded_stand_in: tuple[StandInGame, Path], monkeypatch: pytest.MonkeyPatch
) -> Generator[StandInGame]:
    """Install the stand-in as a command in this process (its dist-info on ``sys.path``).

    Yields:
        The stand-in game; its package is forgotten afterwards, so no later test finds it.

    """
    game, _recording = recorded_stand_in
    monkeypatch.syspath_prepend(game.install_directory)
    try:
        yield game
    finally:
        sys.modules.pop(game.package, None)


@pytest.fixture(scope='module')
def recorded_chiming_stand_in(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[StandInGame, Path]:
    """Record the chiming stand-in (a plain ``Sound.play()`` on CHIME_FRAME) once per module.

    Returns:
        The stand-in game and its recording (each test copies it before reading it).

    """
    root = tmp_path_factory.mktemp('inner-game-chime')
    game = write_chiming_stand_in_game(
        directory=root / 'site-packages',
        package=CHIMING_STAND_IN_PACKAGE,
        chime_on_frame=CHIME_FRAME,
    )
    recording = record_stand_in_game_once(game=game, path=root / 'recorded.jsonl.gz')
    return game, recording


@pytest.fixture
def chiming_stand_in(
    recorded_chiming_stand_in: tuple[StandInGame, Path], monkeypatch: pytest.MonkeyPatch
) -> Generator[StandInGame]:
    """Install the chiming stand-in as a command in this process.

    Yields:
        The stand-in game; its package is forgotten afterwards.

    """
    game, _recording = recorded_chiming_stand_in
    monkeypatch.syspath_prepend(game.install_directory)
    try:
        yield game
    finally:
        sys.modules.pop(game.package, None)


@pytest.fixture
def chiming_recording(recorded_chiming_stand_in: tuple[StandInGame, Path], tmp_path: Path) -> Path:
    """Return this test's own copy of the chiming stand-in's recording.

    Returns:
        The copy's path.

    """
    _game, shared_recording = recorded_chiming_stand_in
    return copy_recording(recording=shared_recording, path=tmp_path / 'chime.jsonl.gz')


@pytest.fixture(scope='module')
def recorded_live_voice_stand_in(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[StandInGame, Path]:
    """Record the live-voice stand-in (a live voice from LIVE_VOICE_FRAME on) once per module.

    Returns:
        The stand-in game and its recording (each test copies it before reading it).

    """
    root = tmp_path_factory.mktemp('inner-game-projector')
    game = write_live_voice_stand_in_game(
        directory=root / 'site-packages',
        package=LIVE_VOICE_STAND_IN_PACKAGE,
        live_voice_on_frame=LIVE_VOICE_FRAME,
    )
    recording = record_stand_in_game_once(game=game, path=root / 'recorded.jsonl.gz')
    return game, recording


@pytest.fixture
def live_voice_stand_in(
    recorded_live_voice_stand_in: tuple[StandInGame, Path], monkeypatch: pytest.MonkeyPatch
) -> Generator[StandInGame]:
    """Install the live-voice stand-in as a command in this process.

    Yields:
        The stand-in game; its package is forgotten afterwards.

    """
    game, _recording = recorded_live_voice_stand_in
    monkeypatch.syspath_prepend(game.install_directory)
    try:
        yield game
    finally:
        sys.modules.pop(game.package, None)


@pytest.fixture
def live_voice_recording(
    recorded_live_voice_stand_in: tuple[StandInGame, Path], tmp_path: Path
) -> Path:
    """Return this test's own copy of the live-voice stand-in's recording.

    Returns:
        The copy's path.

    """
    _game, shared_recording = recorded_live_voice_stand_in
    return copy_recording(recording=shared_recording, path=tmp_path / 'projector.jsonl.gz')


@pytest.fixture(scope='module')
def recorded_small_channels_stand_in(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[StandInGame, Path]:
    """Record a stand-in with --sound-channels 6 --live-voice-pool 2, once per module.

    Returns:
        The stand-in game and its recording (each test copies it before reading it).

    """
    root = tmp_path_factory.mktemp('inner-game-small-channels')
    game = write_stand_in_game(
        directory=root / 'site-packages', package=SMALL_CHANNELS_STAND_IN_PACKAGE
    )
    recording = record_stand_in_game_once(
        game=game,
        path=root / 'recorded.jsonl.gz',
        extra_arguments=(
            '--sound-channels',
            str(SMALL_LIBRARY_CHANNELS),
            '--live-voice-pool',
            str(SMALL_LIVE_POOL),
        ),
    )
    return game, recording


@pytest.fixture
def small_channels_stand_in(
    recorded_small_channels_stand_in: tuple[StandInGame, Path], monkeypatch: pytest.MonkeyPatch
) -> Generator[StandInGame]:
    """Install the small-channels stand-in as a command in this process.

    Yields:
        The stand-in game; its package is forgotten afterwards.

    """
    game, _recording = recorded_small_channels_stand_in
    monkeypatch.syspath_prepend(game.install_directory)
    try:
        yield game
    finally:
        sys.modules.pop(game.package, None)


@pytest.fixture
def small_channels_recording(
    recorded_small_channels_stand_in: tuple[StandInGame, Path], tmp_path: Path
) -> Path:
    """Return this test's own copy of the small-channels stand-in's recording.

    Returns:
        The copy's path.

    """
    _game, shared_recording = recorded_small_channels_stand_in
    return copy_recording(recording=shared_recording, path=tmp_path / 'small.jsonl.gz')


@pytest.fixture(autouse=True)
def outer_partition() -> Generator[ChannelPartition]:
    """Partition the mixer as an outer game's engine does, and declare the inner games' channels.

    As a host does at startup, before anything plays (``reserve_inner_game_channels``: the
    mixer grows once), so every test's inner games can be built; every channel idle.

    Yields:
        The outer partition; every channel is stopped afterwards, so no sound outlives the test.

    """
    pygame.mixer.stop()
    partition = reserve_channels(
        live_pool=LIVE_POOL, library_channels=LIBRARY_CHANNELS, legacy_channels=LEGACY_CHANNELS
    )
    reserve_inner_game_channels(games=DECLARED_INNER_GAMES)
    try:
        yield partition
    finally:
        pygame.mixer.stop()


@pytest.fixture(scope='module')
def recorded_too_big_stand_in(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[StandInGame, Path]:
    """Record a stand-in with --sound-channels 33 (more than a heard set), once per module.

    Returns:
        The stand-in game and its recording (each test copies it before reading it).

    """
    root = tmp_path_factory.mktemp('inner-game-too-big')
    game = write_stand_in_game(directory=root / 'site-packages', package=TOO_BIG_STAND_IN_PACKAGE)
    recording = record_stand_in_game_once(
        game=game,
        path=root / 'recorded.jsonl.gz',
        extra_arguments=('--sound-channels', str(TOO_BIG_LIBRARY_CHANNELS)),
    )
    return game, recording


@pytest.fixture
def too_big_stand_in(
    recorded_too_big_stand_in: tuple[StandInGame, Path], monkeypatch: pytest.MonkeyPatch
) -> Generator[StandInGame]:
    """Install the too-big stand-in as a command in this process.

    Yields:
        The stand-in game; its package is forgotten afterwards.

    """
    game, _recording = recorded_too_big_stand_in
    monkeypatch.syspath_prepend(game.install_directory)
    try:
        yield game
    finally:
        sys.modules.pop(game.package, None)


@pytest.fixture
def too_big_recording(recorded_too_big_stand_in: tuple[StandInGame, Path], tmp_path: Path) -> Path:
    """Return this test's own copy of the too-big stand-in's recording.

    Returns:
        The copy's path.

    """
    _game, shared_recording = recorded_too_big_stand_in
    return copy_recording(recording=shared_recording, path=tmp_path / 'too-big.jsonl.gz')


@pytest.fixture(scope='module')
def recorded_big_pool_stand_in(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[StandInGame, Path]:
    """Record a stand-in with --live-voice-pool 5 (more than declared per game), once per module.

    A replay takes its recording's options (only replay-local ones are this run's), so the pool
    is the recording's: an argument given to the inner game would not change it.

    Returns:
        The stand-in game and its recording (each test copies it before reading it).

    """
    root = tmp_path_factory.mktemp('inner-game-big-pool')
    game = write_stand_in_game(directory=root / 'site-packages', package=BIG_POOL_STAND_IN_PACKAGE)
    recording = record_stand_in_game_once(
        game=game,
        path=root / 'recorded.jsonl.gz',
        extra_arguments=('--live-voice-pool', str(BIG_LIVE_POOL)),
    )
    return game, recording


@pytest.fixture
def big_pool_stand_in(
    recorded_big_pool_stand_in: tuple[StandInGame, Path], monkeypatch: pytest.MonkeyPatch
) -> Generator[StandInGame]:
    """Install the big-pool stand-in as a command in this process.

    Yields:
        The stand-in game; its package is forgotten afterwards.

    """
    game, _recording = recorded_big_pool_stand_in
    monkeypatch.syspath_prepend(game.install_directory)
    try:
        yield game
    finally:
        sys.modules.pop(game.package, None)


@pytest.fixture
def recording(recorded_stand_in: tuple[StandInGame, Path], tmp_path: Path) -> Path:
    """Return this test's own copy of the stand-in's recording.

    Returns:
        The copy's path.

    """
    _game, shared_recording = recorded_stand_in
    return copy_recording(recording=shared_recording, path=tmp_path / 'replay.jsonl.gz')


@pytest.fixture
def sentinel_in_sdl_queue() -> Generator[pygame.event.Event]:
    """Leave one event in SDL's otherwise empty queue for the test's length.

    Yields:
        The event; the queue is emptied afterwards.

    """
    pygame.event.clear()
    sentinel = pygame.event.Event(SENTINEL_EVENT_TYPE, {'marker': 'outer'})
    pygame.event.post(sentinel)
    try:
        yield sentinel
    finally:
        pygame.event.clear()


@pytest.fixture
def outer_blocked_types() -> Generator[dict[int, bool]]:
    """Set an outer game's own blocked event types at SDL; put back what was there afterwards.

    Yields:
        Each type's blocked state as the outer game set it.

    """
    changed_types = (*OUTER_BLOCKED_TYPES, *OUTER_ALLOWED_TYPES)
    before = {event_type: pygame.event.get_blocked(event_type) for event_type in changed_types}
    pygame.event.set_blocked(list(OUTER_BLOCKED_TYPES))
    pygame.event.set_allowed(list(OUTER_ALLOWED_TYPES))
    try:
        yield blocked_states(event_types=changed_types)
    finally:
        pygame.event.set_blocked([
            event_type for event_type, was_blocked in before.items() if was_blocked
        ])
        pygame.event.set_allowed([
            event_type for event_type, was_blocked in before.items() if not was_blocked
        ])


def blocked_states(*, event_types: tuple[int, ...]) -> dict[int, bool]:
    """Return SDL's blocked state for each event type.

    Args:
        event_types: The types to read.

    Returns:
        Each type's ``pygame.event.get_blocked``.

    """
    return {event_type: pygame.event.get_blocked(event_type) for event_type in event_types}


def process_state() -> dict[str, object]:
    """Return what an inner game must leave as it found it in the process.

    Returns:
        SDL's blocked input types, the window's size and caption, SDL's driver variables, the
        current context and the default context's engine.

    """
    window = pygame.display.get_surface()
    assert window is not None
    return {
        'blocked': {
            event_type: pygame.event.get_blocked(event_type)
            for event_type in (*REAL_INPUT_EVENT_TYPES, pygame.QUIT)
        },
        'window_size': window.get_size(),
        'caption': pygame.display.get_caption(),
        'drivers': tuple(os.environ.get(variable) for variable in SDL_DRIVER_VARIABLES),
        'context': current_context(),
        'engine': default_context().value(slot=CURRENT_ENGINE_SLOT).engine,
    }


def queued_without_pumping() -> list[tuple[int, dict[str, object]]]:
    """Take every event in SDL's queue without pumping it (nothing new is read from the OS).

    Returns:
        Each event's type and attributes, in order.

    """
    return [(event.type, dict(event.dict)) for event in pygame.event.get(pump=False)]


def play_to_the_end(inner_game: InnerGame) -> int:
    """Step an inner game until it ends or fails.

    Returns:
        How many steps returned True.

    """
    for running_steps in range(MOST_STEPS):
        if not inner_game.step():
            return running_steps
    pytest.fail(f'{inner_game.context.name} did not end in {MOST_STEPS} steps')


def reservation() -> tuple[int, list[int]]:
    """Return the mixer's reservation: as the engine remembers it, and as SDL picks channels.

    The host declared the inner games' channels before the test (``outer_partition``), so an
    inner build moves nothing: the legacy channels stay above them. Every channel must be idle.

    Returns:
        ``reserved_channel_count()`` (the outer partition's) and the channels ``Sound.play()``
        would get.

    """
    return reserved_channel_count(), unreserved_channel_ids()


def inner_partition(inner_game: InnerGame) -> ChannelPartition | None:
    """Return the inner game's partition (its context's), or None when it holds none.

    Returns:
        The partition.

    """
    return inner_game.context.value(slot=INNER_CHANNELS_SLOT).partition


def heard_set_of(inner_game: InnerGame) -> int | None:
    """Return the first channel of the heard set the inner game holds.

    Returns:
        The channel index, or None while it holds none.

    """
    with inner_game.context.active():
        return heard_set_start()


def busy_channel_ids() -> list[int]:
    """Return every mixer channel that is playing.

    Returns:
        Their indices.

    """
    return [
        index
        for index in range(pygame.mixer.get_num_channels())
        if pygame.mixer.Channel(index).get_busy()
    ]


def chime_channel(inner_game: InnerGame) -> pygame.mixer.Channel | None:
    """Return what the chiming stand-in's ``Sound.play()`` returned.

    Returns:
        The channel it played on, or None (no free channel, or it has not chimed yet).

    """
    with inner_game.context.active():
        scene = SceneManager().active_scene
    channel = vars(scene)['chime_channel']  # the stand-in's own attribute
    assert channel is None or isinstance(channel, pygame.mixer.Channel)
    return channel


def step_past_the_chime(inner_game: InnerGame) -> None:
    """Step the chiming stand-in until its chime frame has run."""
    for _step in range(CHIME_FRAME + 1):
        assert inner_game.step()


def replay_stand_in(
    *,
    game: StandInGame,
    path: Path,
    name: str = 'tile',
    size: tuple[int, int] = TARGET_SIZE,
    arguments: tuple[str, ...] = QUIET,
) -> InnerGame:
    """Start the stand-in's replay as an inner game.

    Returns:
        The inner game.

    """
    return InnerGame.replay(
        command=game.console_script, path=path, name=name, size=size, arguments=arguments
    )


@pytest.fixture(scope='module')
def recorded_spawning_stand_in(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[StandInGame, Path]:
    """Record the spawning stand-in (a /sprite spawn on SPAWN_FRAME) once per module.

    Returns:
        The stand-in game and its recording (each test copies it before reading it).

    """
    root = tmp_path_factory.mktemp('inner-game-spawn')
    game = write_spawning_stand_in_game(
        directory=root / 'site-packages',
        package=SPAWNING_STAND_IN_PACKAGE,
        spawn_on_frame=SPAWN_FRAME,
    )
    recording = record_stand_in_game_once(game=game, path=root / 'recorded.jsonl.gz')
    return game, recording


@pytest.fixture
def spawning_stand_in(
    recorded_spawning_stand_in: tuple[StandInGame, Path], monkeypatch: pytest.MonkeyPatch
) -> Generator[StandInGame]:
    """Install the spawning stand-in as a command in this process.

    Yields:
        The stand-in game; its package is forgotten afterwards.

    """
    game, _recording = recorded_spawning_stand_in
    monkeypatch.syspath_prepend(game.install_directory)
    try:
        yield game
    finally:
        sys.modules.pop(game.package, None)


class TestASpriteSpawnInsideATile:
    """A recording that used /sprite replays inside a tile: the sprite joins the tile's scene."""

    def test_an_inner_game_replays_a_spawn_into_its_own_scene(
        self,
        spawning_stand_in: StandInGame,
        recorded_spawning_stand_in: tuple[StandInGame, Path],
        tmp_path: Path,
    ):
        """The tile's scene gets the sprite at its point; the outer game's scene gets nothing."""
        _game, shared_recording = recorded_spawning_stand_in
        recording = copy_recording(recording=shared_recording, path=tmp_path / 'spawn.jsonl.gz')
        # The outer game's scene, where a spawn handled in the wrong context would land
        outer_scene_manager = SceneManager()
        outer_active_scene = outer_scene_manager.active_scene
        outer_scene = Scene(options={})
        outer_scene_manager.active_scene = outer_scene
        try:
            inner_game = replay_stand_in(game=spawning_stand_in, path=recording)
            for _step in range(SPAWN_FRAME + 1):
                assert inner_game.step()
            with inner_game.context.active():
                inner_scene = SceneManager().active_scene
            assert inner_scene is not None
            spawned = [
                sprite for sprite in inner_scene.all_sprites if isinstance(sprite, SpawnedSprite)
            ]
            play_to_the_end(inner_game)
        finally:
            outer_scene_manager.active_scene = outer_active_scene

        assert [(sprite.world_x, sprite.world_y) for sprite in spawned] == [
            (STAND_IN_SPAWN_POINT[0] - 2, STAND_IN_SPAWN_POINT[1] - 1)
        ]
        assert inner_game.outcome.diverged is False, inner_game.outcome.report
        assert not any(isinstance(sprite, SpawnedSprite) for sprite in outer_scene.all_sprites)


class TestAReplayInsideItsContext:
    """The command's own entry point replays the recording in the inner game's context."""

    def test_it_plays_to_its_end_and_matches(self, stand_in: StandInGame, recording: Path):
        """Every frame runs, the replay matches, and the outcome says so."""
        inner_game = replay_stand_in(game=stand_in, path=recording)

        assert inner_game.outcome == InnerGameOutcome(
            state=InnerGameState.RUNNING, frames_run=0, report=None, diverged=None, error=None
        )
        running_steps = play_to_the_end(inner_game)

        outcome = inner_game.outcome
        assert outcome.state is InnerGameState.ENDED, outcome
        assert outcome.diverged is False
        assert outcome.error is None
        assert outcome.report is not None
        assert outcome.report.startswith('Replay matched'), outcome.report
        # The step that ran the last frame returned False: the game ended there
        assert outcome.frames_run == running_steps + 1
        assert inner_game.context.name == 'tile'
        assert current_context() is default_context()

    def test_it_draws_on_its_own_surface_of_the_size_asked_for(
        self, stand_in: StandInGame, recording: Path
    ):
        """The surface is the context's render target, in the display's format."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        inner_game.step()
        with inner_game.context.active():
            target = render_target()

        surface = inner_game.surface
        display = pygame.display.get_surface()
        assert display is not None
        assert surface.get_size() == TARGET_SIZE
        assert surface.get_bitsize() == display.get_bitsize()
        assert surface is not display
        assert target is surface
        inner_game.finish()

    def test_finishing_is_idempotent_and_steps_after_it_run_nothing(
        self, stand_in: StandInGame, recording: Path
    ):
        """finish() twice gives the same outcome; a step after it returns False and runs nothing."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        play_to_the_end(inner_game)

        first = inner_game.finish()
        second = inner_game.finish()

        assert first == second == inner_game.outcome
        assert not inner_game.step()
        assert inner_game.outcome == first

    def test_finishing_before_the_end_ends_it_with_where_it_stopped(
        self, stand_in: StandInGame, recording: Path
    ):
        """The host may end a replay early: ENDED, its report the length divergence."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        inner_game.step()

        outcome = inner_game.finish()

        assert outcome.state is InnerGameState.ENDED
        assert outcome.frames_run == 1
        assert outcome.diverged is True
        assert outcome.report is not None
        assert outcome.report.startswith('Replay diverged at frame 1'), outcome.report

    def test_an_unfinished_game_without_an_engine_raises_instead_of_asserting(
        self, stand_in: StandInGame, recording: Path
    ):
        """step() and finish() on an unfinished game with no engine raise a named error."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        real_engine = inner_game._engine
        inner_game._engine = None

        with pytest.raises(InnerGameStateError, match='no engine'):
            inner_game.step()
        with pytest.raises(InnerGameStateError, match='no engine'):
            inner_game.finish()

        inner_game._engine = real_engine
        inner_game.finish()

    def test_finishing_an_engine_without_replay_sources_fails_the_game_with_a_named_error(
        self, stand_in: StandInGame, recording: Path
    ):
        """An inner game always replays; if its engine has no replay sources, finish says so."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        assert inner_game._engine is not None
        inner_game._engine.replay_sources = None

        outcome = inner_game.finish()

        assert outcome.state is InnerGameState.FAILED
        assert outcome.error is not None
        assert 'no replay sources' in outcome.error

    def test_building_an_inner_game_registers_nothing_with_pygames_quit(
        self, stand_in: StandInGame, recording: Path, mocker: MockerFixture
    ):
        """Pygame cannot unregister a quit callback, so each tile would add one for good."""
        register_quit = mocker.patch('pygame.register_quit')

        first = replay_stand_in(game=stand_in, path=recording, name='first')
        second = replay_stand_in(game=stand_in, path=recording, name='second')

        register_quit.assert_not_called()
        first.finish()
        second.finish()

    def test_a_game_whose_timer_failed_to_start_still_finishes(
        self, stand_in: StandInGame, recording: Path, mocker: MockerFixture
    ):
        """The engine runs without a timer when its backend fails (injected): nothing to close."""
        mocker.patch(
            'glitchygames.engine.game_engine.create_timer', side_effect=ValueError('no timer')
        )
        inner_game = replay_stand_in(game=stand_in, path=recording)

        play_to_the_end(inner_game)

        assert inner_game.outcome.state is InnerGameState.ENDED, inner_game.outcome
        assert inner_game.outcome.report is not None
        assert inner_game.outcome.report.startswith('Replay matched')

    def test_two_inner_games_play_side_by_side(self, stand_in: StandInGame, recording: Path):
        """Stepped in turn, each in its own context, both match."""
        first = replay_stand_in(game=stand_in, path=recording, name='first')
        second = replay_stand_in(game=stand_in, path=recording, name='second')

        for _step in range(MOST_STEPS):
            first_running = first.step()
            second_running = second.step()
            if not (first_running or second_running):
                break

        for inner_game in (first, second):
            outcome = inner_game.outcome
            assert outcome.state is InnerGameState.ENDED, outcome
            assert outcome.report is not None
            assert outcome.report.startswith('Replay matched'), outcome.report
        assert first.context is not second.context


class TestWhatAHostNeedsToPaceIt:
    """The recorded duration of the next frame, the frame count and the frame index."""

    @staticmethod
    def make_uneven(*, recording: Path) -> list[float]:
        """Give the recording a different ``dt`` on every frame.

        Returns:
            The new ``dt`` of each frame, in order.

        """
        new_durations: list[float] = []

        def change(trace: dict[str, Any]) -> None:
            for position, frame in enumerate(trace['frames']):
                frame['dt'] = 0.010 + 0.001 * position
                new_durations.append(frame['dt'])

        rewrite_recording(recording_path=recording, change=change)
        return new_durations

    def test_the_next_frames_duration_follows_the_viewers_rule_on_uneven_dts(
        self, stand_in: StandInGame, recording: Path
    ):
        """The next frame's recorded dt; the current frame's for the last; 0.0 past the end."""
        durations = self.make_uneven(recording=recording)
        inner_game = replay_stand_in(game=stand_in, path=recording)

        assert inner_game.frame_count == len(durations)
        seen: list[tuple[int, float]] = []
        while True:
            seen.append((inner_game.frame_index, inner_game.next_frame_seconds))
            if not inner_game.step():
                break

        for frame_index, seconds in seen:
            if frame_index + 1 < len(durations):
                assert seconds == pytest.approx(durations[frame_index + 1])
            elif frame_index < len(durations):
                assert seconds == pytest.approx(durations[frame_index])
        assert seen[0][1] == pytest.approx(durations[1])
        assert seen[-1][0] <= len(durations)
        assert inner_game.next_frame_seconds == 0.0

    def test_the_frame_index_is_the_next_frame_and_equals_the_frames_run(
        self, stand_in: StandInGame, recording: Path
    ):
        """Before frame 0 it is 0; each step adds one; it always equals outcome.frames_run."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        assert inner_game.frame_index == 0

        while inner_game.step():
            assert inner_game.frame_index == inner_game.outcome.frames_run
        assert inner_game.frame_index == inner_game.outcome.frames_run
        assert inner_game.frame_index == inner_game.frame_count

    def test_all_three_read_as_defined_after_the_game_ended_early(
        self, stand_in: StandInGame, recording: Path
    ):
        """A game finished before the end still answers by the recording it replayed."""
        durations = self.make_uneven(recording=recording)
        inner_game = replay_stand_in(game=stand_in, path=recording)
        inner_game.step()
        inner_game.finish()

        assert inner_game.frame_count == len(durations)
        assert inner_game.frame_index == 1
        assert inner_game.next_frame_seconds == pytest.approx(durations[2])

    def test_an_engine_without_replay_sources_has_no_frames_to_report(
        self, stand_in: StandInGame, recording: Path
    ):
        """Nothing to read the recording from: 0 frames and 0.0 seconds, not an error."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        assert inner_game._engine is not None
        replay_sources = inner_game._engine.replay_sources
        inner_game._engine.replay_sources = None

        assert inner_game.frame_count == 0
        assert inner_game.next_frame_seconds == 0.0

        inner_game._engine.replay_sources = replay_sources
        inner_game.finish()

    def test_a_game_that_failed_to_build_has_no_frames(self, recording: Path):
        """No installed command: nothing recorded is known, so 0 frames and 0.0 seconds."""
        inner_game = InnerGame.replay(
            command='no-such-command-anywhere', path=recording, name='tile', size=TARGET_SIZE
        )

        assert inner_game.outcome.state is InnerGameState.FAILED
        assert inner_game.frame_count == 0
        assert inner_game.frame_index == 0
        assert inner_game.next_frame_seconds == 0.0


class CountsFrames(Protocol):
    """What the frame-cost clock reads: an inner game, or a counter standing in for one."""

    @property
    def frame_index(self) -> int:
        """The frames run so far."""
        ...


class FrameCounter:
    """A frame index set by hand, to check the frame-cost clock against ``TickBudget``."""

    def __init__(self) -> None:
        """Start at frame 0."""
        self.frame_index = 0


def frame_cost_clock(inner_game: CountsFrames) -> Callable[[], float]:
    """Return a fake real-time clock on which every frame the inner game runs costs one frame.

    A ``TickBudget`` of ``FRAME_COST_SECONDS`` on it is spent by exactly one frame, so a test
    says how many frames a budget allows without reading the wall clock.

    Returns:
        The clock: the frames run so far, times ``FRAME_COST_SECONDS``.

    """
    return lambda: inner_game.frame_index * FRAME_COST_SECONDS


def frame_budget(*, inner_game: CountsFrames, frame_count: float) -> TickBudget:
    """Start a budget allowing ``frame_count`` frames on the frame-cost clock.

    Returns:
        The budget, started now.

    """
    return TickBudget(
        length_seconds=frame_count * FRAME_COST_SECONDS,
        measured_seconds=frame_cost_clock(inner_game),
    )


def fast_forward_in_slices(
    *, inner_game: InnerGame, to_frame: int, frames_per_slice: float
) -> list[int]:
    """Fast-forward in calls of a fresh budget each, as a host does once per tick, until reached.

    Returns:
        How many frames each call ran, in order.

    """
    frames_run_by_call: list[int] = []
    for _call in range(MOST_STEPS):
        frames_before = inner_game.frame_index
        reached = inner_game.fast_forward(
            to_frame=to_frame,
            budget=frame_budget(inner_game=inner_game, frame_count=frames_per_slice),
        )
        frames_run_by_call.append(inner_game.frame_index - frames_before)
        assert inner_game.frame_index <= to_frame
        if reached:
            return frames_run_by_call
    pytest.fail(f'{inner_game.context.name} did not reach frame {to_frame} in {MOST_STEPS} calls')


def test_the_frame_cost_clock_spends_a_k_frame_budget_in_exactly_k_frames():
    """The double's own contract, for every start frame of a long recording.

    ``TickBudget.is_spent`` compares a difference of clock readings with the length, so a frame
    cost that floats cannot hold exactly (0.004) lets a "one-frame" budget run two frames from
    some start frames; the tests above would then count frames the fast-forward never chose.
    """
    counter = FrameCounter()
    wrong: list[tuple[int, int]] = []
    for start_frame in range(FRAME_COST_CHECKED_START_FRAMES):
        for budget_frames in FRAME_COST_CHECKED_BUDGET_FRAMES:
            counter.frame_index = start_frame
            budget = frame_budget(inner_game=counter, frame_count=budget_frames)
            counter.frame_index = start_frame + budget_frames - 1
            spent_a_frame_early = budget.is_spent
            counter.frame_index = start_frame + budget_frames
            if spent_a_frame_early or not budget.is_spent:
                wrong.append((start_frame, budget_frames))

    assert wrong == []


class TestAFastForward:
    """A silent, time-sliced fast-forward to a frame (Arcade sub-plan 5, decision 8).

    ``fast_forward(to_frame=..., budget=...)`` runs the frames from the next one up to
    ``to_frame`` until the budget is spent, at least one a call, and says whether it got there;
    the next call goes on. The budgets here run on a fake clock on which each frame costs
    ``FRAME_COST_SECONDS`` (``frame_cost_clock``).
    """

    def test_one_call_with_a_large_budget_reaches_the_frame_and_the_next_step_runs_it(
        self, stand_in: StandInGame, recording: Path
    ):
        """Every frame before ``to_frame`` runs in one call; the next step runs ``to_frame``."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        to_frame = inner_game.frame_count // 2

        reached = inner_game.fast_forward(
            to_frame=to_frame,
            budget=frame_budget(inner_game=inner_game, frame_count=inner_game.frame_count),
        )

        assert reached is True
        assert inner_game.frame_index == to_frame
        assert inner_game.outcome.state is InnerGameState.RUNNING
        assert inner_game.step()
        assert inner_game.frame_index == to_frame + 1
        assert current_context() is default_context()
        inner_game.finish()

    def test_a_budget_of_one_frame_takes_one_call_a_frame(
        self, stand_in: StandInGame, recording: Path
    ):
        """``to_frame`` calls, each running exactly one frame, never past ``to_frame``."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        to_frame = inner_game.frame_count // 2

        frames_run_by_call = fast_forward_in_slices(
            inner_game=inner_game, to_frame=to_frame, frames_per_slice=1
        )

        assert frames_run_by_call == [1] * to_frame
        assert inner_game.frame_index == to_frame
        inner_game.finish()

    def test_a_spent_budget_still_runs_one_frame_a_call(
        self, stand_in: StandInGame, recording: Path
    ):
        """Progress is guaranteed: a budget spent before the call still runs one frame."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        to_frame = SLICED_TO_FRAME

        frames_run_by_call = fast_forward_in_slices(
            inner_game=inner_game, to_frame=to_frame, frames_per_slice=0
        )

        assert frames_run_by_call == [1] * to_frame
        inner_game.finish()

    def test_a_budget_of_several_frames_stops_at_the_frame_not_past_it(
        self, stand_in: StandInGame, recording: Path
    ):
        """Slices of three frames toward a frame not a multiple of three: the last is shorter."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        to_frame = SLICED_TO_FRAME

        frames_run_by_call = fast_forward_in_slices(
            inner_game=inner_game, to_frame=to_frame, frames_per_slice=FRAMES_PER_SLICE
        )

        assert to_frame % FRAMES_PER_SLICE
        assert frames_run_by_call == [FRAMES_PER_SLICE] * (to_frame // FRAMES_PER_SLICE) + [
            to_frame % FRAMES_PER_SLICE
        ]
        assert inner_game.frame_index == to_frame
        inner_game.finish()

    def test_every_frame_after_it_is_a_headless_replays(
        self,
        stand_in: StandInGame,
        recording: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """The proof's check: digests equal a headless replay's, pixels the game's alone.

        Every frame's digest (those it fast-forwarded through and those after) equals the
        recording replayed alone, headless, in a child; every frame from ``to_frame`` on draws
        what the recording replayed alone as an inner game draws.
        """
        use_stand_in_game(install_directory=stand_in.install_directory, monkeypatch=monkeypatch)
        reference = reference_digests(
            console_script=stand_in.console_script, recording=recording, work_directory=tmp_path
        )
        alone = play_alone(
            console_script=stand_in.console_script, recording=recording, work_directory=tmp_path
        )
        tile = Tile(
            console_script=stand_in.console_script,
            recording=recording,
            name='fast-forwarded',
            work_directory=tmp_path,
        )
        to_frame = tile.inner_game.frame_count // 2

        frames_run_by_call = fast_forward_in_slices(
            inner_game=tile.inner_game, to_frame=to_frame, frames_per_slice=FRAMES_PER_SLICE
        )
        while tile.running:
            tile.run_frames(frame_count=1)

        assert sum(frames_run_by_call) == to_frame
        assert tile.matched_digests() == reference
        assert len(tile.pixel_hashes) == len(alone.pixel_hashes) - to_frame
        assert tile.pixel_hashes == alone.pixel_hashes[to_frame:]

    @pytest.mark.parametrize(
        ('stand_in_name', 'recording_name', 'sounding_frame'),
        [
            ('chiming_stand_in', 'chiming_recording', CHIME_FRAME),
            ('live_voice_stand_in', 'live_voice_recording', LIVE_VOICE_FRAME),
        ],
    )
    def test_nothing_it_runs_is_heard(
        self,
        stand_in_name: str,
        recording_name: str,
        sounding_frame: int,
        tmp_path: Path,
        request: pytest.FixtureRequest,
    ):
        """Through a chime's frame and a live voice's start: no channel heard, live chunks at 0."""
        game: StandInGame = request.getfixturevalue(stand_in_name)
        sounding_recording: Path = request.getfixturevalue(recording_name)
        tile = Tile(
            console_script=game.console_script,
            recording=sounding_recording,
            name='fast-forwarded',
            work_directory=tmp_path,
        )
        to_frame = sounding_frame + FRAMES_PER_SLICE * 2

        for _call in range(MOST_STEPS):
            reached = tile.inner_game.fast_forward(
                to_frame=to_frame, budget=frame_budget(inner_game=tile.inner_game, frame_count=1)
            )
            assert_no_tile_is_heard(tiles=(tile,))
            if reached:
                break

        assert tile.inner_game.frame_index == to_frame
        tile.inner_game.finish()

    def test_a_chime_it_runs_through_never_reaches_a_channel(
        self, chiming_stand_in: StandInGame, chiming_recording: Path
    ):
        """The chime's play returned None: not even heard for a moment inside the call."""
        inner_game = replay_stand_in(game=chiming_stand_in, path=chiming_recording)
        before = reservation()

        reached = inner_game.fast_forward(
            to_frame=CHIME_FRAME + 1,
            budget=frame_budget(inner_game=inner_game, frame_count=inner_game.frame_count),
        )

        assert reached is True
        assert chime_channel(inner_game) is None
        assert busy_channel_ids() == []
        assert reservation() == before
        inner_game.finish()

    def test_an_audible_game_is_refused_naming_the_call_that_silences_it(
        self, stand_in: StandInGame, recording: Path
    ):
        """Refused before any frame runs; the error names ``set_audible(audible=False)``."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        inner_game.set_audible(audible=True)

        with pytest.raises(InnerGameAudibleError, match=r'set_audible\(audible=False\)'):
            inner_game.fast_forward(
                to_frame=SLICED_TO_FRAME,
                budget=frame_budget(inner_game=inner_game, frame_count=SLICED_TO_FRAME),
            )

        assert inner_game.frame_index == 0
        assert inner_game.audible is True
        inner_game.set_audible(audible=False)
        assert inner_game.fast_forward(
            to_frame=SLICED_TO_FRAME,
            budget=frame_budget(inner_game=inner_game, frame_count=SLICED_TO_FRAME),
        )
        inner_game.finish()

    @pytest.mark.parametrize('frames_past_the_last', [0, 1])
    def test_a_frame_at_or_past_the_frame_count_is_a_value_error(
        self, stand_in: StandInGame, recording: Path, frames_past_the_last: int
    ):
        """The recording has no such frame to stand at: refused, nothing run."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        to_frame = inner_game.frame_count + frames_past_the_last

        with pytest.raises(ValueError, match='frame count'):
            inner_game.fast_forward(
                to_frame=to_frame, budget=frame_budget(inner_game=inner_game, frame_count=1)
            )

        assert inner_game.frame_index == 0
        inner_game.finish()

    def test_a_negative_frame_is_a_value_error(self, stand_in: StandInGame, recording: Path):
        """No frame comes before frame 0: refused, nothing run."""
        inner_game = replay_stand_in(game=stand_in, path=recording)

        with pytest.raises(ValueError, match='frame count'):
            inner_game.fast_forward(
                to_frame=-1, budget=frame_budget(inner_game=inner_game, frame_count=1)
            )

        assert inner_game.frame_index == 0
        inner_game.finish()

    def test_a_divergence_on_the_way_ends_it_with_that_outcome_and_it_is_not_reached(
        self, stand_in: StandInGame, recording: Path
    ):
        """A tampered frame before ``to_frame``: ENDED, diverged, reported, and False."""
        tamper_first_sprite_rect(recording_path=recording, frame_number=TAMPERED_FRAME)
        inner_game = replay_stand_in(game=stand_in, path=recording)
        to_frame = inner_game.frame_count - 1
        assert to_frame > TAMPERED_FRAME

        reached = inner_game.fast_forward(
            to_frame=to_frame,
            budget=frame_budget(inner_game=inner_game, frame_count=inner_game.frame_count),
        )

        outcome = inner_game.outcome
        assert reached is False
        assert outcome.state is InnerGameState.ENDED, outcome
        assert outcome.diverged is True
        assert outcome.report is not None
        assert outcome.report.startswith(f'Replay diverged at frame {TAMPERED_FRAME}')
        assert inner_game.frame_index < to_frame
        assert current_context() is default_context()

    def test_a_failure_on_the_way_ends_it_with_that_outcome_and_it_is_not_reached(
        self, stand_in: StandInGame, recording: Path, mocker: MockerFixture
    ):
        """The scene raising on a frame before ``to_frame``: FAILED with its error, and False."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        inner_game.step()
        with inner_game.context.active():
            scene = SceneManager().active_scene
        assert isinstance(scene, Scene)
        # An injected failure, from the second frame on
        mocker.patch.object(scene, 'dt_tick', side_effect=RuntimeError('the scene broke'))

        reached = inner_game.fast_forward(
            to_frame=SLICED_TO_FRAME,
            budget=frame_budget(inner_game=inner_game, frame_count=SLICED_TO_FRAME),
        )

        assert reached is False
        assert inner_game.outcome.state is InnerGameState.FAILED
        assert inner_game.outcome.error == 'RuntimeError: the scene broke'
        assert inner_game.frame_index == 1
        # A finished game goes no further: still not reached, and nothing runs
        assert (
            inner_game.fast_forward(
                to_frame=SLICED_TO_FRAME, budget=frame_budget(inner_game=inner_game, frame_count=1)
            )
            is False
        )
        assert inner_game.frame_index == 1

    def test_a_frame_already_passed_is_a_no_op(self, stand_in: StandInGame, recording: Path):
        """At or past ``to_frame``: no frame runs, even with a spent budget, and it is reached."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        for _step in range(SLICED_TO_FRAME):
            assert inner_game.step()

        at_the_frame = inner_game.fast_forward(
            to_frame=SLICED_TO_FRAME, budget=frame_budget(inner_game=inner_game, frame_count=0)
        )
        past_the_frame = inner_game.fast_forward(
            to_frame=SLICED_TO_FRAME - 1, budget=frame_budget(inner_game=inner_game, frame_count=0)
        )

        assert at_the_frame is True
        assert past_the_frame is True
        assert inner_game.frame_index == SLICED_TO_FRAME
        inner_game.finish()

    def test_a_game_that_ended_is_not_at_its_frame_though_it_passed_it(
        self, stand_in: StandInGame, recording: Path
    ):
        """Played to its end: no next frame runs, so a frame it passed is not reached (False)."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        play_to_the_end(inner_game)

        reached = inner_game.fast_forward(
            to_frame=SLICED_TO_FRAME, budget=frame_budget(inner_game=inner_game, frame_count=1)
        )

        assert reached is False
        assert inner_game.frame_index == inner_game.frame_count


class TestARecordedQuit:
    """Review Focus 1: the recording's quit ends only its inner game."""

    def test_it_ends_the_inner_game_and_never_reaches_sdl(
        self,
        stand_in: StandInGame,
        recording: Path,
        sentinel_in_sdl_queue: pygame.event.Event,
    ):
        """ENDED and matched; SDL's queue holds only the outer game's event; no outer quit."""
        outer_scene_manager = SceneManager()
        outer_quit_requested = outer_scene_manager.quit_requested
        inner_game = replay_stand_in(game=stand_in, path=recording)

        play_to_the_end(inner_game)

        assert inner_game.outcome.state is InnerGameState.ENDED
        assert queued_without_pumping() == [
            (sentinel_in_sdl_queue.type, dict(sentinel_in_sdl_queue.dict))
        ]
        assert SceneManager() is outer_scene_manager
        assert outer_scene_manager.quit_requested == outer_quit_requested


class TestADivergence:
    """Review Focus 2: a replay that diverges inside an inner game ends it, reported."""

    def test_it_ends_with_the_report_and_writes_nothing_to_stdout(
        self,
        stand_in: StandInGame,
        recording: Path,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ):
        """ENDED (not FAILED) with the divergence report, logged at INFO; stdout empty."""
        tamper_first_sprite_rect(recording_path=recording, frame_number=TAMPERED_FRAME)
        capsys.readouterr()
        caplog.set_level('INFO', logger='game.inner_game')

        inner_game = replay_stand_in(game=stand_in, path=recording)
        play_to_the_end(inner_game)

        outcome = inner_game.outcome
        assert outcome.state is InnerGameState.ENDED, outcome
        assert outcome.diverged is True
        assert outcome.error is None
        assert outcome.report is not None
        assert outcome.report.startswith(f'Replay diverged at frame {TAMPERED_FRAME}')
        assert not capsys.readouterr().out
        assert any(
            record.levelname == 'INFO' and outcome.report in record.getMessage()
            for record in caplog.records
        )


class TestAFailure:
    """Review Focus 3: a game that raises or exits fails alone; the default context goes on."""

    def test_a_replay_refused_while_building_fails_with_its_exit(
        self,
        stand_in: StandInGame,
        recording: Path,
        sentinel_in_sdl_queue: pygame.event.Event,
    ):
        """A target of another size than recorded: the replay's refusal (a SystemExit) is FAILED.

        Nothing is left behind: no engine current in the inner context, nothing in the process.
        """
        before = process_state()

        inner_game = replay_stand_in(game=stand_in, path=recording, size=ANOTHER_SIZE)

        outcome = inner_game.outcome
        assert outcome.state is InnerGameState.FAILED
        assert outcome.frames_run == 0
        assert outcome.report is None
        assert outcome.diverged is None
        assert outcome.error == 'the game exited with UNUSABLE_INPUT (65)'
        assert not inner_game.step()
        assert inner_game.finish() == outcome
        with inner_game.context.active():
            assert current_context().value(slot=CURRENT_ENGINE_SLOT).engine is None
        assert process_state() == before
        assert queued_without_pumping() == [
            (sentinel_in_sdl_queue.type, dict(sentinel_in_sdl_queue.dict))
        ]

    def test_an_argument_the_game_refuses_fails_with_its_exit(
        self, stand_in: StandInGame, recording: Path
    ):
        """An unknown flag: argparse's own exit is FAILED, never the host's exit."""
        inner_game = replay_stand_in(
            game=stand_in, path=recording, arguments=(*QUIET, '--no-such-flag')
        )

        assert inner_game.outcome.state is InnerGameState.FAILED
        assert inner_game.outcome.error == 'the game exited with ARGUMENT_PARSER_ERROR (2)'
        assert current_context() is default_context()

    @pytest.mark.parametrize('removed', ['--ai', '--no-ai'])
    def test_the_removed_ai_switch_fails_as_an_unknown_argument(
        self, stand_in: StandInGame, recording: Path, removed: str
    ):
        """The refused-argument check names neither, so the game's own parser refuses it."""
        assert refused_arguments(arguments=(removed,)) == []

        inner_game = replay_stand_in(game=stand_in, path=recording, arguments=(*QUIET, removed))

        assert inner_game.outcome.state is InnerGameState.FAILED
        assert inner_game.outcome.error == 'the game exited with ARGUMENT_PARSER_ERROR (2)'
        assert current_context() is default_context()

    def test_a_game_raising_while_stepping_fails_alone(
        self,
        stand_in: StandInGame,
        recording: Path,
        mocker: MockerFixture,
        sentinel_in_sdl_queue: pygame.event.Event,
    ):
        """The raising game is FAILED with its error; the other inner game goes on and matches."""
        before = process_state()
        failing = replay_stand_in(game=stand_in, path=recording, name='failing')
        healthy = replay_stand_in(game=stand_in, path=recording, name='healthy')
        failing.step()
        healthy.step()
        with failing.context.active():
            scene = SceneManager().active_scene
        assert isinstance(scene, Scene)
        # An injected failure, on the failing game's scene alone
        mocker.patch.object(scene, 'dt_tick', side_effect=RuntimeError('the scene broke'))

        assert not failing.step()
        play_to_the_end(healthy)

        failed = failing.outcome
        assert failed.state is InnerGameState.FAILED
        assert failed.error == 'RuntimeError: the scene broke'
        assert failed.frames_run == 1
        assert failed.report is not None
        assert failed.report.startswith('Replay stopped at frame'), failed.report
        assert 'the run ended with RuntimeError: the scene broke' in failed.report
        assert healthy.outcome.state is InnerGameState.ENDED
        assert healthy.outcome.report is not None
        assert healthy.outcome.report.startswith('Replay matched')
        with failing.context.active():
            assert current_context().value(slot=CURRENT_ENGINE_SLOT).engine is None
        assert process_state() == before
        assert queued_without_pumping() == [
            (sentinel_in_sdl_queue.type, dict(sentinel_in_sdl_queue.dict))
        ]

    def test_a_game_exiting_while_stepping_fails_alone(
        self, stand_in: StandInGame, recording: Path, mocker: MockerFixture
    ):
        """A game's own sys.exit() in a frame is FAILED, never the host's exit."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        inner_game.step()
        with inner_game.context.active():
            scene = SceneManager().active_scene
        mocker.patch.object(scene, 'dt_tick', side_effect=SystemExit(0))

        assert not inner_game.step()

        assert inner_game.outcome.state is InnerGameState.FAILED
        assert inner_game.outcome.error == 'the game exited with SUCCESS (0)'

    def test_a_game_exiting_without_a_number_is_described_as_it_exited(
        self, stand_in: StandInGame, recording: Path, mocker: MockerFixture
    ):
        """sys.exit('message') carries no exit code: the outcome names what it carried."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        inner_game.step()
        with inner_game.context.active():
            scene = SceneManager().active_scene
        mocker.patch.object(scene, 'dt_tick', side_effect=SystemExit('gave up'))

        inner_game.step()

        assert inner_game.outcome.error == "the game exited with SystemExit('gave up')"

    def test_a_failing_finish_is_failed_and_the_rest_of_the_finish_still_runs(
        self, stand_in: StandInGame, recording: Path, mocker: MockerFixture
    ):
        """end_frames raising: FAILED with its error; the replay is still settled and reported."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        inner_game.step()
        mocker.patch.object(SceneManager, 'end_frames', side_effect=RuntimeError('no end'))

        outcome = inner_game.finish()

        assert outcome.state is InnerGameState.FAILED
        assert outcome.error == 'RuntimeError: no end'
        assert outcome.report is not None
        assert outcome.report.startswith('Replay stopped at frame 1')
        assert current_context() is default_context()

    def test_a_failure_while_finishing_a_failed_game_keeps_the_first_error(
        self, stand_in: StandInGame, recording: Path, mocker: MockerFixture
    ):
        """The step's error stays the outcome's; the finish's own failure is only logged."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        inner_game.step()
        with inner_game.context.active():
            scene = SceneManager().active_scene
        mocker.patch.object(scene, 'dt_tick', side_effect=RuntimeError('first'))
        mocker.patch.object(SceneManager, 'end_frames', side_effect=RuntimeError('second'))

        inner_game.step()

        assert inner_game.outcome.state is InnerGameState.FAILED
        assert inner_game.outcome.error == 'RuntimeError: first'

    def test_a_game_failing_to_begin_its_frames_is_finished(
        self,
        stand_in: StandInGame,
        recording: Path,
        mocker: MockerFixture,
        sentinel_in_sdl_queue: pygame.event.Event,
    ):
        """Built, then begin_frames raising: FAILED, and the run finished as any other (rule 4).

        The frames end, the recording and the timer close and the replay's result is settled;
        no engine is left current in the inner context, and nothing in the process changed.
        """
        before = process_state()
        mocker.patch.object(SceneManager, 'begin_frames', side_effect=RuntimeError('no frames'))
        end_frames = mocker.spy(SceneManager, 'end_frames')
        stop_trace_recording = mocker.spy(GameEngine, 'stop_trace_recording')

        inner_game = replay_stand_in(game=stand_in, path=recording)

        outcome = inner_game.outcome
        assert outcome.state is InnerGameState.FAILED
        assert outcome.error == 'RuntimeError: no frames'
        assert outcome.frames_run == 0
        assert outcome.diverged is True
        assert outcome.report is not None
        assert outcome.report.startswith('Replay stopped at frame 0'), outcome.report
        assert 'the run ended with RuntimeError: no frames' in outcome.report
        end_frames.assert_called_once()
        stop_trace_recording.assert_called_once()
        assert not inner_game.step()
        assert inner_game.finish() == outcome
        with inner_game.context.active():
            assert current_context().value(slot=CURRENT_ENGINE_SLOT).engine is None
        assert current_context() is default_context()
        assert process_state() == before
        assert queued_without_pumping() == [
            (sentinel_in_sdl_queue.type, dict(sentinel_in_sdl_queue.dict))
        ]

    def test_a_keyboard_interrupt_is_not_contained(
        self, stand_in: StandInGame, recording: Path, mocker: MockerFixture
    ):
        """Ctrl-C is the host's (decision 4): it propagates out of step()."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        inner_game.step()
        with inner_game.context.active():
            scene = SceneManager().active_scene
        mocker.patch.object(scene, 'dt_tick', side_effect=KeyboardInterrupt)

        with pytest.raises(KeyboardInterrupt):
            inner_game.step()
        assert current_context() is default_context()

    def test_an_unknown_command_fails(self, recording: Path):
        """No installed command of that name: FAILED, saying so."""
        inner_game = InnerGame.replay(
            command='no-such-inner-game', path=recording, name='tile', size=TARGET_SIZE
        )

        assert inner_game.outcome.state is InnerGameState.FAILED
        assert inner_game.outcome.error == "no installed command is named 'no-such-inner-game'"

    def test_a_command_that_starts_no_engine_fails(
        self, recording: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """An entry point that returns without starting a game: FAILED, saying so."""
        install_directory = tmp_path / 'site-packages'
        package_directory = install_directory / COMMAND_THAT_STARTS_NOTHING_PACKAGE
        package_directory.mkdir(parents=True)
        (package_directory / '__init__.py').write_text(
            'def main():\n    """Start nothing."""\n', encoding='utf-8'
        )
        write_stand_in_distribution(
            directory=install_directory,
            distribution=COMMAND_THAT_STARTS_NOTHING,
            console_scripts={
                COMMAND_THAT_STARTS_NOTHING: f'{COMMAND_THAT_STARTS_NOTHING_PACKAGE}:main'
            },
        )
        monkeypatch.syspath_prepend(install_directory)
        monkeypatch.delitem(sys.modules, COMMAND_THAT_STARTS_NOTHING_PACKAGE, raising=False)

        inner_game = InnerGame.replay(
            command=COMMAND_THAT_STARTS_NOTHING, path=recording, name='tile', size=TARGET_SIZE
        )
        sys.modules.pop(COMMAND_THAT_STARTS_NOTHING_PACKAGE, None)

        assert inner_game.outcome.state is InnerGameState.FAILED
        assert inner_game.outcome.error == (
            f'{COMMAND_THAT_STARTS_NOTHING} started no game engine in its context'
        )


class TestTheProcessAfterwards:
    """An inner game leaves the process as it found it (no leftovers once it has finished)."""

    def test_a_finished_inner_game_leaves_the_process_as_it_was(
        self,
        stand_in: StandInGame,
        recording: Path,
        sentinel_in_sdl_queue: pygame.event.Event,
    ):
        """Blocked types, SDL's queue, the window, the drivers, sys.argv, the default context."""
        before = process_state()
        argv_before = list(sys.argv)

        inner_game = replay_stand_in(game=stand_in, path=recording)
        play_to_the_end(inner_game)

        assert process_state() == before
        assert queued_without_pumping() == [
            (sentinel_in_sdl_queue.type, dict(sentinel_in_sdl_queue.dict))
        ]
        with inner_game.context.active():
            assert current_context().value(slot=CURRENT_ENGINE_SLOT).engine is None
        assert sys.argv == argv_before

    def test_the_outer_games_blocked_event_types_survive_building_stepping_and_finishing(
        self, stand_in: StandInGame, recording: Path, outer_blocked_types: dict[int, bool]
    ):
        """Row S6: the inner engine's and its managers' allowing changes nothing at SDL.

        The outer game blocks the controller events and the mouse wheel and allows SYSWMEVENT,
        none of them the engine's own choice: after the build, a step and the finish, each is
        as the outer game set it.
        """
        event_types = tuple(outer_blocked_types)

        inner_game = replay_stand_in(game=stand_in, path=recording)
        after_build = blocked_states(event_types=event_types)
        inner_game.step()
        after_step = blocked_states(event_types=event_types)
        inner_game.finish()
        after_finish = blocked_states(event_types=event_types)

        assert inner_game.outcome.state is InnerGameState.ENDED, inner_game.outcome
        assert after_build == outer_blocked_types
        assert after_step == outer_blocked_types
        assert after_finish == outer_blocked_types
        assert outer_blocked_types[pygame.MOUSEWHEEL] is True
        assert outer_blocked_types[pygame.SYSWMEVENT] is False


class TestRefusals:
    """Decision 5: only recordings run inner; what would do anything else is refused first."""

    @pytest.mark.parametrize(
        'arguments',
        [
            ('--record-trace', 'new.jsonl.gz'),
            ('--replay-trace', 'other.jsonl.gz'),
            ('--rebaseline', 'new.jsonl.gz'),
            ('--audit',),
            ('--compare-trace', 'old.jsonl.gz'),
            ('--verify',),
            ('--measure',),
            ('--record-session', 'new.jsonl.gz'),
            ('--replay-frame-stream', '1234:token'),
            ('--replay-restart-handoff', 'handoff.json'),
            ('--replay-viewer-state', '{}'),
            ('--profile',),
            ('--list-input-devices',),
            ('--help',),
            ('-h',),
            ('-p',),
            ('-v',),
            ('--version',),
            ('--ver',),
            ('-ph',),
            ('-wp',),
            ('-wv',),
            ('--rebase', 'new.jsonl.gz'),
            ('--record-trace=new.jsonl.gz',),
            ('--log-level', 'error', '--audit'),
        ],
    )
    def test_it_is_refused_before_anything_is_built(
        self, stand_in: StandInGame, recording: Path, arguments: tuple[str, ...]
    ):
        """InnerGameRefusedError naming the argument; the command's package is never imported."""
        with pytest.raises(InnerGameRefusedError, match='cannot run inside another game'):
            replay_stand_in(game=stand_in, path=recording, arguments=arguments)

        assert stand_in.package not in sys.modules
        assert current_context() is default_context()

    @pytest.mark.parametrize('arguments', [('--sound-cache', 'ram'), ('--sound-cache=ram',)])
    def test_an_engine_flag_that_begins_a_refused_flag_is_itself(
        self, stand_in: StandInGame, recording: Path, arguments: tuple[str, ...]
    ):
        """Argparse takes an exact flag before any abbreviation: --sound-cache is the cache mode.

        It begins --sound-cache-list and the other sound-cache tools' flags, all refused; an
        abbreviation only they share is still one of them, so it is refused.
        """
        inner_game = replay_stand_in(game=stand_in, path=recording, arguments=arguments)

        play_to_the_end(inner_game)

        assert inner_game.outcome.state is InnerGameState.ENDED, inner_game.outcome
        assert is_refused_argument(argument='--sound-cache-l')
        assert is_refused_argument(argument='--sound-cache-fi')

    def test_a_cluster_whose_value_holds_a_refused_letter_is_the_games(
        self, stand_in: StandInGame, recording: Path
    ):
        """-l takes the rest of its cluster as its value: no letter after it is a flag."""
        inner_game = replay_stand_in(game=stand_in, path=recording, arguments=('-lerror',))

        play_to_the_end(inner_game)

        assert inner_game.outcome.state is InnerGameState.ENDED, inner_game.outcome
        assert not is_refused_short_flag_cluster(cluster='fp')
        assert not is_refused_short_flag_cluster(cluster='rhv')
        assert is_refused_short_flag_cluster(cluster='wph')

    def test_no_engine_flag_is_refused_but_the_refused_ones(self):
        """Every flag of the engine's parser: refused exactly when it is a refused flag.

        ``--no-audit`` (the audit switched off) is allowed though ``--audit`` is refused.

        Also the short letters: the engine's short forms of refused flags are refused letters,
        and the engine's short flags that take a value are exactly SHORT_FLAGS_TAKING_A_VALUE.
        """
        parser = GameEngine.args(argparse.ArgumentParser())
        wrongly_judged: list[str] = []
        value_letters: set[str] = set()
        for action in parser._actions:
            long_flags = [flag for flag in action.option_strings if flag.startswith('--')]
            short_flags = [flag for flag in action.option_strings if not flag.startswith('--')]
            should_refuse = any(flag in REFUSED_FLAGS for flag in long_flags)
            # A long flag on its own (--no-audit, the audit switched off, may run); a short
            # flag as its action's long flags are
            wrongly_judged.extend(
                flag
                for flag in long_flags
                if is_refused_argument(argument=flag) != (flag in REFUSED_FLAGS)
            )
            wrongly_judged.extend(
                flag for flag in short_flags if is_refused_argument(argument=flag) != should_refuse
            )
            if action.nargs != 0:
                value_letters.update(flag[1:] for flag in short_flags)
            if should_refuse:
                assert {flag[1:] for flag in short_flags} <= REFUSED_SHORT_FLAG_LETTERS

        assert wrongly_judged == []
        assert value_letters == SHORT_FLAGS_TAKING_A_VALUE

    def test_the_refusal_names_every_refused_argument(self, stand_in: StandInGame, recording: Path):
        """Each refused argument is named once, in the order given."""
        with pytest.raises(InnerGameRefusedError) as refusal:
            replay_stand_in(
                game=stand_in, path=recording, arguments=('--audit', '--profile=yes', '--audit')
            )

        assert str(refusal.value) == (
            '--audit, --profile=yes cannot run inside another game: an inner game only replays '
            'a recording headless'
        )

    def test_arguments_after_a_bare_separator_are_the_games(
        self, stand_in: StandInGame, recording: Path
    ):
        """After ``--`` nothing is a flag (argparse's rule): the game gets them as positionals."""
        inner_game = replay_stand_in(
            game=stand_in, path=recording, arguments=(*QUIET, '--', '--audit')
        )

        # The stand-in takes no positional: argparse refuses it, which is the game's failure
        assert inner_game.outcome.state is InnerGameState.FAILED
        assert inner_game.outcome.error == 'the game exited with ARGUMENT_PARSER_ERROR (2)'


class TestPlainSoundPlays:
    """Decisions 1 and 2 of plans/2026-11-13-arcade-4-sound.md: a silent game's plain plays.

    A new inner game is silent; while it builds, steps or finishes, every channel is reserved,
    so its plain ``Sound.play()`` finds none free and returns None (nothing starts). The
    reservation is put back after each call. An audible inner game is heard.
    """

    def test_a_new_inner_game_is_silent_and_the_default_context_stays_audible(
        self, stand_in: StandInGame, recording: Path
    ):
        """The inner context's route is silent from its creation; switching it is the host's."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        with inner_game.context.active():
            silent_reading = is_audible()

        inner_game.set_audible(audible=True)
        with inner_game.context.active():
            audible_reading = is_audible()
        inner_game.set_audible(audible=False)

        assert silent_reading is False
        assert audible_reading is True
        assert inner_game.audible is False
        assert is_audible()
        inner_game.finish()

    def test_a_silent_games_sound_play_reaches_no_channel(
        self, chiming_stand_in: StandInGame, chiming_recording: Path
    ):
        """The chime's play returns None, no channel plays, and the reservation is as before.

        After the build, after the chime's step and after the finish.
        """
        before = reservation()

        inner_game = replay_stand_in(game=chiming_stand_in, path=chiming_recording)
        after_build = reservation()
        step_past_the_chime(inner_game)
        busy_after_the_chime = busy_channel_ids()
        channel = chime_channel(inner_game)
        after_steps = reservation()
        inner_game.finish()

        assert channel is None
        assert busy_after_the_chime == []
        assert not pygame.mixer.get_busy()
        assert after_build == before
        assert after_steps == before
        assert reservation() == before
        assert inner_game.outcome.state is InnerGameState.ENDED, inner_game.outcome

    def test_a_silent_step_that_raises_still_puts_the_reservation_back(
        self, chiming_stand_in: StandInGame, chiming_recording: Path, mocker: MockerFixture
    ):
        """The chime's frame raising after its play: FAILED, nothing playing, reservation back."""
        before = reservation()
        inner_game = replay_stand_in(game=chiming_stand_in, path=chiming_recording)
        with inner_game.context.active():
            scene = SceneManager().active_scene
        assert isinstance(scene, Scene)
        scene_dt_tick = scene.dt_tick

        def chime_then_raise(dt: float) -> None:
            scene_dt_tick(dt)
            if vars(scene)['frames'] == CHIME_FRAME:  # the stand-in's own frame count
                message = 'the scene broke after its chime'
                raise RuntimeError(message)

        # An injected failure, in the chime's own frame
        mocker.patch.object(scene, 'dt_tick', side_effect=chime_then_raise)

        play_to_the_end(inner_game)

        assert inner_game.outcome.state is InnerGameState.FAILED
        assert inner_game.outcome.error == 'RuntimeError: the scene broke after its chime'
        assert vars(scene)['chime_channel'] is None
        assert busy_channel_ids() == []
        assert reservation() == before

    def test_an_audible_games_sound_play_is_heard(
        self, chiming_stand_in: StandInGame, chiming_recording: Path
    ):
        """Switched audible before its chime: the play takes a channel, which plays."""
        before = reservation()
        inner_game = replay_stand_in(game=chiming_stand_in, path=chiming_recording)

        inner_game.set_audible(audible=True)
        step_past_the_chime(inner_game)

        channel = chime_channel(inner_game)
        assert inner_game.audible is True
        assert channel is not None
        assert channel.get_busy()
        assert busy_channel_ids() == [channel.id]
        channel.stop()
        inner_game.finish()
        assert reservation() == before

    def test_a_heard_games_plain_sound_stops_when_it_is_switched_away_from(
        self, chiming_stand_in: StandInGame, chiming_recording: Path
    ):
        """Decision 6: its chime stops at once; the outer's plain sound beside it plays on.

        The game then goes on silent: it still matches its recording to its end.
        """
        outer_sound = pygame.mixer.Sound(buffer=bytes(MIXER_BYTES_PER_SECOND * OUTER_SOUND_SECONDS))
        outer_channel = outer_sound.play()
        assert outer_channel is not None
        inner_game = replay_stand_in(game=chiming_stand_in, path=chiming_recording)
        inner_game.set_audible(audible=True)
        step_past_the_chime(inner_game)
        channel = chime_channel(inner_game)
        assert channel is not None
        busy_while_heard = busy_channel_ids()

        inner_game.set_audible(audible=False)
        busy_after_the_switch = busy_channel_ids()
        play_to_the_end(inner_game)

        assert busy_while_heard == sorted([outer_channel.id, channel.id])
        assert busy_after_the_switch == [outer_channel.id]
        assert outer_channel.get_sound() is outer_sound
        assert inner_game.outcome.state is InnerGameState.ENDED, inner_game.outcome
        assert inner_game.outcome.diverged is False

    def test_a_heard_games_plain_sound_stops_when_it_finishes(
        self, chiming_stand_in: StandInGame, chiming_recording: Path
    ):
        """Finishing goes silent first (rule 6): the chime still playing is stopped."""
        inner_game = replay_stand_in(game=chiming_stand_in, path=chiming_recording)
        inner_game.set_audible(audible=True)
        step_past_the_chime(inner_game)
        channel = chime_channel(inner_game)
        assert channel is not None
        busy_while_heard = busy_channel_ids()

        inner_game.finish()

        assert busy_while_heard == [channel.id]
        assert busy_channel_ids() == []

    def test_the_outer_games_sound_plays_on_through_a_silent_games_steps(
        self, chiming_stand_in: StandInGame, chiming_recording: Path
    ):
        """Review Focus 1: the outer's plain play keeps its channel and plays; nothing joins it."""
        outer_sound = pygame.mixer.Sound(buffer=bytes(MIXER_BYTES_PER_SECOND * OUTER_SOUND_SECONDS))
        outer_channel = outer_sound.play()
        assert outer_channel is not None

        inner_game = replay_stand_in(game=chiming_stand_in, path=chiming_recording)
        step_past_the_chime(inner_game)
        busy_after_the_chime = busy_channel_ids()
        channel = chime_channel(inner_game)
        inner_game.finish()

        assert channel is None
        assert busy_after_the_chime == [outer_channel.id]
        assert outer_channel.get_busy()
        assert outer_channel.get_sound() is outer_sound


class TestInnerChannels:
    """Decisions 4, 5 and 7: the channels the host declared; an inner build never partitions.

    Review Focus 3 (a tile's live voice beside the outer's) and 5 (a recording's own sizes).
    """

    def test_an_inner_build_takes_a_live_pool_and_never_partitions_or_grows_the_mixer(
        self,
        stand_in: StandInGame,
        recording: Path,
        outer_partition: ChannelPartition,
        mocker: MockerFixture,
    ):
        """Logical slots (its recording's 32) and a live pool; the outer's reservation as it was."""
        before = reservation()
        partition_calls = mocker.spy(voices, 'reserve_channels')
        set_num_channels = mocker.spy(pygame.mixer, 'set_num_channels')

        inner_game = replay_stand_in(game=stand_in, path=recording)
        partition = inner_partition(inner_game)
        with inner_game.context.active():
            engine = current_context().value(slot=CURRENT_ENGINE_SLOT).engine
        after_build = reservation()
        play_to_the_end(inner_game)

        assert partition is not None
        assert engine is not None
        assert engine.channel_partition == partition
        assert partition.library == tuple(range(LIBRARY_CHANNELS))
        assert partition.plays_on_a_heard_set
        assert len(partition.live) == LIVE_POOL
        assert not set(partition.live) & {*outer_partition.live, *outer_partition.library}
        partition_calls.assert_not_called()
        set_num_channels.assert_not_called()
        assert after_build == before
        assert reservation() == before

    def test_a_recordings_own_channel_options_size_its_partition(
        self,
        small_channels_stand_in: StandInGame,
        small_channels_recording: Path,
    ):
        """Review Focus 5: --sound-channels 6 --live-voice-pool 2; the outer's unchanged."""
        before = reservation()

        inner_game = replay_stand_in(game=small_channels_stand_in, path=small_channels_recording)
        partition = inner_partition(inner_game)
        after_build = reservation()
        play_to_the_end(inner_game)

        assert partition is not None
        assert partition.library == tuple(range(SMALL_LIBRARY_CHANNELS))
        assert len(partition.live) == SMALL_LIVE_POOL
        assert after_build == before
        assert reservation() == before
        assert inner_game.outcome.state is InnerGameState.ENDED, inner_game.outcome

    def test_two_inner_games_hold_their_own_live_pools(
        self, stand_in: StandInGame, recording: Path, tmp_path: Path
    ):
        """Two tiles at once: their live pools share no channel."""
        second_recording = copy_recording(recording=recording, path=tmp_path / 'second.jsonl.gz')
        first = replay_stand_in(game=stand_in, path=recording, name='first')
        second = replay_stand_in(game=stand_in, path=second_recording, name='second')
        first_partition = inner_partition(first)
        second_partition = inner_partition(second)
        first.finish()
        second.finish()

        assert first_partition is not None
        assert second_partition is not None
        assert not set(first_partition.live) & set(second_partition.live)

    def test_a_finished_inner_games_channels_are_free_and_its_audio_engine_gone(
        self, stand_in: StandInGame, recording: Path, tmp_path: Path
    ):
        """Decision 7: finish discards the audio engine and frees what the next one takes."""
        finished = replay_stand_in(game=stand_in, path=recording, name='finished')
        with finished.context.active():
            audio_engine = SceneManager().audio  # made as a game's first sound would make it
        finished_partition = inner_partition(finished)
        finished.set_audible(audible=True)
        play_to_the_end(finished)
        next_recording = copy_recording(recording=recording, path=tmp_path / 'next.jsonl.gz')

        next_game = replay_stand_in(game=stand_in, path=next_recording, name='next')

        assert audio_engine is not None
        assert finished_partition is not None
        assert inner_partition(finished) is None
        assert heard_set_of(finished) is None
        assert finished.audible is False
        assert finished.context.value(slot=AUDIO_ENGINE_SLOT).engine is None
        assert inner_partition(next_game) == finished_partition
        next_game.finish()

    def test_a_build_with_no_channels_declared_fails_alone(
        self, stand_in: StandInGame, recording: Path
    ):
        """No reserve_inner_game_channels: FAILED, naming the call; nothing held afterwards."""
        release_channels()
        reserve_channels(
            live_pool=LIVE_POOL, library_channels=LIBRARY_CHANNELS, legacy_channels=LEGACY_CHANNELS
        )

        inner_game = replay_stand_in(game=stand_in, path=recording)

        assert inner_game.outcome.state is InnerGameState.FAILED
        assert inner_game.outcome.error is not None
        assert inner_game.outcome.error.startswith('InnerGameChannelsError: no channels')
        assert 'reserve_inner_game_channels' in inner_game.outcome.error
        assert current_context() is default_context()

    def test_a_build_past_the_declared_count_fails_alone_and_frees_its_failed_part(
        self, stand_in: StandInGame, recording: Path, tmp_path: Path
    ):
        """Every declared game running: the next fails alone; the running ones go on."""
        running = [
            replay_stand_in(
                game=stand_in,
                path=copy_recording(recording=recording, path=tmp_path / f'{index}.jsonl.gz'),
                name=f'running {index}',
            )
            for index in range(DECLARED_INNER_GAMES)
        ]

        refused = replay_stand_in(game=stand_in, path=recording, name='one too many')
        still_running = [inner_game.step() for inner_game in running]
        for inner_game in running:
            play_to_the_end(inner_game)

        assert refused.outcome.state is InnerGameState.FAILED
        assert refused.outcome.error is not None
        assert f'all {DECLARED_INNER_GAMES} inner games declared' in refused.outcome.error
        # The contexts still holding the pools are named (a host that dropped one unfinished)
        assert "'running 0', 'running 1', 'running 2'" in refused.outcome.error
        assert inner_partition(refused) is None
        assert still_running == [True] * DECLARED_INNER_GAMES
        assert all(game.outcome.state is InnerGameState.ENDED for game in running)

    def test_a_build_that_fails_gives_its_channels_back(
        self, stand_in: StandInGame, recording: Path, tmp_path: Path
    ):
        """A replay refused after its engine took a live pool: the pool is free for the next."""
        failed = replay_stand_in(game=stand_in, path=recording, size=ANOTHER_SIZE, name='failed')
        next_recording = copy_recording(recording=recording, path=tmp_path / 'next.jsonl.gz')
        next_game = replay_stand_in(game=stand_in, path=next_recording, name='next')
        next_partition = inner_partition(next_game)
        next_game.finish()

        assert failed.outcome.state is InnerGameState.FAILED
        assert inner_partition(failed) is None
        assert next_partition is not None
        assert next_partition.live == (100, 101, 102, 103)

    def test_a_failing_release_is_the_games_failure_and_the_rest_still_runs(
        self, stand_in: StandInGame, recording: Path, tmp_path: Path, mocker: MockerFixture
    ):
        """discard_audio_engine raising at finish: FAILED, and the channels are still given back."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        partition = inner_partition(inner_game)
        # An injected failure in the finish's audio release
        mocker.patch(
            'glitchygames.inner_game.discard_audio_engine', side_effect=RuntimeError('no discard')
        )

        outcome = inner_game.finish()

        assert outcome.state is InnerGameState.FAILED
        assert outcome.error == 'RuntimeError: no discard'
        assert inner_partition(inner_game) is None
        mocker.stopall()
        next_recording = copy_recording(recording=recording, path=tmp_path / 'next.jsonl.gz')
        next_game = replay_stand_in(game=stand_in, path=next_recording, name='next')
        assert partition is not None
        assert inner_partition(next_game) == partition
        next_game.finish()

    def test_a_live_pool_larger_than_declared_fails_alone(
        self,
        stand_in: StandInGame,
        recording: Path,
        big_pool_stand_in: StandInGame,
        recorded_big_pool_stand_in: tuple[StandInGame, Path],
        tmp_path: Path,
    ):
        """A recording with --live-voice-pool 5 of the 4 declared: FAILED; another runs on."""
        running = replay_stand_in(game=stand_in, path=recording, name='running')
        _game, shared_recording = recorded_big_pool_stand_in
        big_pool_recording = copy_recording(
            recording=shared_recording, path=tmp_path / 'big-pool.jsonl.gz'
        )

        refused = replay_stand_in(game=big_pool_stand_in, path=big_pool_recording, name='refused')
        running_steps = play_to_the_end(running)

        assert refused.outcome.state is InnerGameState.FAILED
        assert refused.outcome.error is not None
        assert refused.outcome.error.startswith('InnerGameChannelsError: --live-voice-pool 5')
        assert running_steps > 0
        assert running.outcome.state is InnerGameState.ENDED, running.outcome

    def test_a_tile_too_big_for_a_heard_set_replays_silent_and_refuses_to_be_heard(
        self, too_big_stand_in: StandInGame, too_big_recording: Path
    ):
        """--sound-channels 33: it matches to its end silent; set_audible(True) is refused."""
        inner_game = replay_stand_in(game=too_big_stand_in, path=too_big_recording)

        with pytest.raises(InnerGameChannelsError, match='--sound-channels 33'):
            inner_game.set_audible(audible=True)
        play_to_the_end(inner_game)

        assert inner_game.audible is False
        assert inner_game.outcome.state is InnerGameState.ENDED, inner_game.outcome
        assert inner_game.outcome.diverged is False

    def test_the_heard_sets_alternate_between_the_heard_games(
        self,
        stand_in: StandInGame,
        recording: Path,
        tmp_path: Path,
        mocker: MockerFixture,
    ):
        """First heard on set A, then the second on set B, then the first on A again: no growth."""
        set_num_channels = mocker.spy(pygame.mixer, 'set_num_channels')
        second_recording = copy_recording(recording=recording, path=tmp_path / 'second.jsonl.gz')
        first = replay_stand_in(game=stand_in, path=recording, name='first')
        second = replay_stand_in(game=stand_in, path=second_recording, name='second')

        first.set_audible(audible=True)
        first_set = heard_set_of(first)
        first.set_audible(audible=False)
        second.set_audible(audible=True)
        second_set = heard_set_of(second)
        second.set_audible(audible=False)
        first.set_audible(audible=True)
        first_set_again = heard_set_of(first)
        play_to_the_end(first)
        play_to_the_end(second)

        assert first_set == outer_heard_set_start(set_number=0)
        assert second_set == outer_heard_set_start(set_number=1)
        assert first_set_again == first_set
        assert heard_set_of(second) is None
        set_num_channels.assert_not_called()

    def test_a_tiles_live_voice_plays_beside_the_outer_ones_on_its_own_pool(
        self,
        live_voice_stand_in: StandInGame,
        live_voice_recording: Path,
        outer_partition: ChannelPartition,
    ):
        """Review Focus 3: both live voices start; distinct channels, both playing.

        The silent tile's chunks play at volume 0 on its live pool; the outer's is heard. The
        finished tile's voice is stopped and its channel idle.
        """
        outer_voice = LiveAudio(channel_indices=outer_partition.live).create_instrument_voice(
            owner='outer scene', instrument=Instrument(wave='sine', live=True), frequency=440.0
        )
        outer_voice.stream.start()

        inner_game = replay_stand_in(game=live_voice_stand_in, path=live_voice_recording)
        for _step in range(LIVE_VOICE_FRAME + 1):
            assert inner_game.step()
            # The outer game's loop feeds its voice every frame (LiveStream.update); unfed, its
            # one chunk runs out on a slow runner and channel 0 reads idle (CircleCI job 3655)
            outer_voice.stream.update()
        partition = inner_partition(inner_game)
        with inner_game.context.active():
            scene = SceneManager().active_scene
        tile_voice = vars(scene)['live_voice']  # the stand-in's own attribute
        busy_while_both_play = busy_channel_ids()
        assert partition is not None
        tile_sound = pygame.mixer.Channel(partition.live[0]).get_sound()
        inner_game.finish()
        busy_after_the_finish = busy_channel_ids()
        outer_voice.stream.stop_now()

        assert isinstance(tile_voice, LiveSoundHandle)
        assert busy_while_both_play == [outer_partition.live[0], partition.live[0]]
        assert tile_sound is not None
        assert tile_sound.get_volume() == 0.0
        assert busy_after_the_finish == [outer_partition.live[0]]
        assert not tile_voice.is_playing
        assert not tile_voice.cancel()  # finished: the tile's finish stopped it


# A host engine's command line: small, quiet, unpaced (it runs one frame, then quits)
HOST_ENGINE_ARGUMENTS = ('--resolution', '320x240', '--log-level', 'warning', '--target-fps', '0')
# The heard sets a late declaration asks for: smaller than the default, so only this call says so
LATE_HEARD_SET_CHANNELS = 16


@pytest.fixture
def engine_run_environment(mocker: MockerFixture) -> Generator[None]:
    """Let the test construct and start a real engine, leaving pygame usable for later tests.

    Yields:
        None, while the environment is in place.

    """
    yield from demo_runs.engine_run_environment(mocker)


@pytest.mark.draws_frames
@pytest.mark.usefixtures('engine_run_environment')
def test_a_declaration_after_game_engine_lies_above_its_partition_and_survives_its_start(
    small_channels_stand_in: StandInGame,
    small_channels_recording: Path,
    mocker: MockerFixture,
):
    """GameEngine(...) without INNER_GAMES, then reserve_inner_game_channels, then start().

    The documented route for other sizes, on a real engine (the golden-trace harness's, whose
    plain window the dummy driver can open). The engine had not partitioned yet (it does as
    ``start()`` makes its event managers), so the declaration has it partition first: the heard
    sets lie above its library, and ``start()``'s own partition finds it made and keeps the
    declaration, so a tile built in the host's first frame is heard on the first heard set.
    """
    release_channels()
    seen: dict[str, object] = {}

    def build_and_hear_a_tile(scene: Scene, dt: float) -> None:
        """The host's first frame: a tile built, made heard, played to its end; then quit."""
        del dt
        inner_game = replay_stand_in(game=small_channels_stand_in, path=small_channels_recording)
        seen['declared'] = voices.inner_game_channels_declared()
        inner_game.set_audible(audible=True)
        seen['heard_set'] = heard_set_of(inner_game)
        play_to_the_end(inner_game)
        seen['outcome'] = inner_game.outcome
        scene.scene_manager.quit()

    host_game = type(
        'LateDeclaringHost',
        (Scene,),
        {'NAME': 'LateDeclaringHost', 'dt_tick': build_and_hear_a_tile},
    )
    mocker.patch.object(sys, 'argv', ['late-declaring-host', *HOST_ENGINE_ARGUMENTS])
    engine = GoldenTraceEngine(game=host_game)
    partition_before_the_declaration = engine.channel_partition

    layout = reserve_inner_game_channels(games=2, heard_set_channels=LATE_HEARD_SET_CHANNELS)
    partition = engine.channel_partition
    engine.start()

    assert partition_before_the_declaration is None
    assert partition is not None
    assert partition.library == tuple(range(LIVE_POOL, LIVE_POOL + LIBRARY_CHANNELS))
    assert engine.channel_partition is partition
    first_heard_set_start = LIVE_POOL + LIBRARY_CHANNELS
    assert layout.heard_sets[0] == tuple(
        range(first_heard_set_start, first_heard_set_start + LATE_HEARD_SET_CHANNELS)
    )
    assert seen['declared'] is True
    assert seen['heard_set'] == first_heard_set_start
    outcome = seen['outcome']
    assert isinstance(outcome, InnerGameOutcome)
    assert outcome.state is InnerGameState.ENDED, outcome
    assert outcome.diverged is False


def outer_heard_set_start(*, set_number: int) -> int:
    """Return the first channel of a heard set, as the outer fixture's declaration laid it out.

    Returns:
        The default partition's 36 channels, then 32 per heard set.

    """
    return LIVE_POOL + LIBRARY_CHANNELS + set_number * LIBRARY_CHANNELS


def build_a_host(*, mocker: MockerFixture, arguments: tuple[str, ...]) -> GoldenTraceEngine:
    """An outer game's engine, built (never started) from a command line: the current engine.

    Returns:
        The engine.
    """
    host_game = type('OptionsHost', (Scene,), {'NAME': 'OptionsHost'})
    mocker.patch.object(sys, 'argv', ['options-host', *arguments])
    return GoldenTraceEngine(game=host_game)


def inner_options(inner_game: InnerGame) -> dict[str, object]:
    """The inner game's engine's options, read in its own context.

    Returns:
        The options.
    """
    engine = inner_game.context.value(slot=CURRENT_ENGINE_SLOT).engine
    assert engine is not None
    return engine.options


@pytest.mark.usefixtures('engine_run_environment')
class TestTheOuterGamesOptions:
    """Rule 1: an inner game is given the outer game's command line, then the host's arguments."""

    def test_an_inner_game_runs_with_the_outer_games_options(
        self, stand_in: StandInGame, recording: Path, mocker: MockerFixture
    ):
        """An Arcade run with --sound-cache none runs its tiles so (no recording overrides it)."""
        build_a_host(mocker=mocker, arguments=('--sound-cache', 'none', *QUIET))

        inner_game = replay_stand_in(game=stand_in, path=recording)
        options = inner_options(inner_game)
        play_to_the_end(inner_game)

        assert inner_game.outcome.state is InnerGameState.ENDED, inner_game.outcome
        assert options['sound_cache'] == 'none'

    @pytest.mark.parametrize(
        'arguments_and_state',
        [
            ((), (), True),
            (('--no-lucid-circuit',), (), False),
            (('--no-lucid-circuit',), ('--lucid-circuit',), True),
            ((), ('--no-lucid-circuit',), False),
        ],
    )
    def test_an_inner_games_feature_flags_are_its_own_command_lines(
        self,
        stand_in: StandInGame,
        recording: Path,
        mocker: MockerFixture,
        arguments_and_state: tuple[tuple[str, ...], tuple[str, ...], bool],
    ):
        """The outer game's flags reach it, its host's own win, and the outer game keeps its own."""
        outer, own, on = arguments_and_state
        build_a_host(mocker=mocker, arguments=(*outer, *QUIET))

        inner_game = replay_stand_in(game=stand_in, path=recording, arguments=own)
        with inner_game.context.active():
            inner_state = flag_state(name='lucid-circuit')
        outer_state = flag_state(name='lucid-circuit')
        play_to_the_end(inner_game)

        assert inner_state.on is on
        assert outer_state.on is not bool(outer)

    def test_the_hosts_own_arguments_win_over_the_outer_games(
        self, stand_in: StandInGame, recording: Path, mocker: MockerFixture
    ):
        """They come last, and argparse keeps the last value given."""
        build_a_host(mocker=mocker, arguments=('--log-level', 'warning'))

        inner_game = replay_stand_in(game=stand_in, path=recording, arguments=QUIET)
        options = inner_options(inner_game)
        play_to_the_end(inner_game)

        assert options['log_level'] == 'error'

    def test_an_outer_game_that_records_itself_still_hosts_its_tiles(
        self, stand_in: StandInGame, recording: Path, mocker: MockerFixture, tmp_path: Path
    ):
        """The outer run's own mode (recording itself) is left out of what its tiles are given.

        So the Arcade can have a golden recording: its tiles replay their own demos, with the
        rest of its options.
        """
        build_a_host(
            mocker=mocker,
            arguments=(
                '--record-trace',
                str(tmp_path / 'arcade.jsonl.gz'),
                '--profile',
                '--sound-cache',
                'none',
                *QUIET,
            ),
        )

        inner_game = replay_stand_in(game=stand_in, path=recording)
        options = inner_options(inner_game)
        play_to_the_end(inner_game)

        assert inner_game.outcome.state is InnerGameState.ENDED, inner_game.outcome
        assert options['sound_cache'] == 'none'
        assert options['record_trace'] is None
        assert options['profile'] is False

    def test_the_hosts_own_refused_arguments_are_still_refused(
        self, stand_in: StandInGame, recording: Path, mocker: MockerFixture
    ):
        """Only the outer game's command line is filtered: a host asking for more is refused."""
        build_a_host(mocker=mocker, arguments=QUIET)

        with pytest.raises(InnerGameRefusedError, match='--profile cannot run inside'):
            replay_stand_in(game=stand_in, path=recording, arguments=('--profile',))

        assert stand_in.package not in sys.modules


@pytest.mark.parametrize(
    ('command_arguments', 'inherited'),
    [
        (('--record-trace', 'arcade.jsonl.gz', '--sound-cache', 'ram'), ('--sound-cache', 'ram')),
        (('--record-trace=arcade.jsonl.gz', '--sound-cache', 'ram'), ('--sound-cache', 'ram')),
        (('--record-t', 'arcade.jsonl.gz', *QUIET), QUIET),
        (('--replay-trace', 'golden.jsonl.gz', '--headless'), ('--headless',)),
        (('--verify', 'a.jsonl.gz', 'b.jsonl.gz', *QUIET), QUIET),
        (('--verify', *QUIET), QUIET),
        (('--audit', '--profile', '--help', '--version', *QUIET), QUIET),
        (('-p', *QUIET), QUIET),
        (('-wp', *QUIET), ('-w', *QUIET)),
        (('-ph',), ()),
        (('-lp',), ('-lp',)),
        (('--sound-cache', 'ram'), ('--sound-cache', 'ram')),
        (('--sound-cache-fill', '--sound-cache', 'ram'), ('--sound-cache', 'ram')),
    ],
    ids=[
        'its value',
        'an inline value',
        'an abbreviation and its value',
        'a replay of the outer game',
        'any number of values',
        'no values',
        'switches',
        'a short switch',
        'a cluster keeps its other letters',
        'a cluster of refused letters',
        'a value holding a refused letter',
        'an engine flag beginning refused ones',
        'a refused flag beginning with an engine one',
    ],
)
def test_the_outer_games_refused_flags_are_left_out_whole(command_arguments, inherited):
    """Each refused flag goes with its values (argparse's count for it); nothing else goes."""
    assert inherited_arguments(command_arguments=command_arguments) == inherited


def test_every_refused_flag_takes_a_value_count_left_out_correctly():
    """A refused flag of a new kind (two values, an optional one) would take the wrong count."""
    actions = engine_option_actions()
    counts = {flag: actions[flag].nargs for flag in REFUSED_FLAGS if flag in actions}

    assert {flag: count for flag, count in counts.items() if count not in FLAG_VALUE_COUNTS} == {}
    assert set(counts.values()) == FLAG_VALUE_COUNTS  # each kind is one a flag has


def test_the_outer_games_positionals_are_never_passed_on():
    """After the outer game's bare ``--`` come its own positionals, never options."""
    assert inherited_arguments(command_arguments=('--sound-cache', 'none', '--', '--audit')) == (
        '--sound-cache',
        'none',
    )
    assert inherited_arguments(command_arguments=()) == ()
