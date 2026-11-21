"""Every golden and bundled demo replays inside an inner game exactly as it does alone.

The proof of Arcade sub-plan 3 (plans/2026-11-12-arcade-3-inner-game.md, Task 4): a game's own
command, unchanged, replays its recording inside an engine context of its own
(glitchygames/inner_game.py) beside another game doing the same, and neither can tell. Each
recording is paired with the next one in the list (``partner_of``), and for each pair:

- **the reference** is the recording replayed alone, headless, in a child process through its
  console script (``replay_recording_headless``) with ``--replay-digest``: one SHA-256 per
  replayed frame (glitchygames/replay/audit.py);
- **the tiles**: both recordings replayed as ``InnerGame``s in this process, stepped unevenly
  interleaved (``INTERLEAVED_STEPS``: not one frame each in turn, so neither keeps pace with
  the other), each with its own ``--replay-digest``. Each tile's digests equal its reference's,
  frame for frame, and it ends matched;
- **the pixels**: each tile's render target, hashed after every frame it ran, equals the same
  recording replayed alone as an ``InnerGame`` (what a tile draws is the game's alone).

Every recording is a tile in its own case; as a partner, a recording that is known to diverge
inside a tile (``DIVERGES_INSIDE_A_TILE``) is passed over for the next one, so it never cuts a
pair short. Its own case is ``xfail(strict=True)``, naming the plans/future-work.md entry: it
fails until the bug is fixed, and then the strict xfail fails, so the mark is removed.

Each pair is played twice (Arcade sub-plan 4, plans/2026-11-13-arcade-4-sound.md, Review Focus 2
and 4): with every tile silent, and with the case's tile switched audible a third of the way
through its recording and silent again two thirds of the way through (``HEARD_FROM_FRACTION``).
Both runs' digests equal the references and both draw what the tile draws alone: a game sees the
same answers heard or silent. Whenever no tile is heard nothing a tile played may sound
(``assert_no_tile_is_heard``): no unreserved channel plays (a silent tile's plain plays reach
none, and a switched-away tile's were stopped) and every chunk on a tile's live pool is at
volume 0. At the switch away, what the tile had sounding is checked off the mixer at once
(``Tile.switch_away``). A tile whose recording plays sounds (``PLAYS_SOUNDS``) must have been
heard while heard, and no other may have played one, so the switched run proves something. A heard
sound is a plain play of the tile's, or a voice on the heard set it holds (the games' sounds
moved onto the sound library: plans/2026-11-14-sound-migration.md), so Review Focus 4's "the
newly heard game's next sound is heard" is shown here for both; live voices' are covered by unit
tests (tests/audio/test_channel_partition.py, tests/audio/test_live.py and
tests/engine/test_inner_game.py).

The outer partitions the mixer and declares its tiles' channels first, as an Arcade does at
startup (``inner_game_channels``). The tiles run inside an outer window of another size than
any of them (``OUTER_WINDOW_SIZE``, an Arcade's): a game that measures the window instead of
its own screen is caught, as it would be in the Arcade. The test display (800x600) is as wide as
the 800x480 demos, and hid Bitmappy's divergence.

The outer game's key repeat (``pygame.key.get_repeat()``: SDL's, one per process) must be the
same after a tile has run (the plan's Review Focus 4: the text-input demo sets its own repeat in
its setup, and the engine's input box another on each key release while it is active). Each
recording is replayed alone as an inner game to check it
(``test_a_tile_leaves_the_outer_key_repeat_as_it_was``); one known to change it
(``CHANGES_THE_OUTER_KEY_REPEAT``) is ``xfail(strict=True)`` with its entry. After every
recording replayed alone, the outer window's size and caption and SDL's blocked event types
(one set per process, row S6 of plans/2026-10-25-engine-context.md) are checked too: the outer
game sets blocked types of its own (``OUTER_BLOCKED_TYPES``, ``OUTER_ALLOWED_TYPES``) that no
engine sets, so a tile allowing every type, or a manager allowing its own, would show.

The same proof through ``DemoPlayer`` (Arcade sub-plan 5,
plans/2026-11-20-arcade-5-playback-core.md, Task 6; glitchygames/demo_player.py): each pair is
replayed as two demo players, as an Arcade's tiles hold them, paced by the elapsed time the test
serves and limited by budgets on a fake real-time clock (``FrameCostClock``: each frame a player
runs costs a fixed time, so a budget allows a known number of frames and the runs are the same on
every machine). Two runs:

- **uneven, looped, fast-forwarded and heard**
  (``test_a_recording_replays_as_a_demo_player_beside_another_as_it_does_alone``): the case's
  player first fast-forwards, in slices, to a poster frame drawn from a seeded stream
  (``poster_frame``, the Arcade's ``random_stream('arcade-posters')`` stood in for by
  ``POSTER_SEED``), then both players are ticked with uneven elapsed time (``UNEVEN_TICKS``)
  and uneven budgets (``INTERLEAVED_STEPS``) until the case's recording has looped and played
  once more from frame 0, heard for the middle third of that second run and switched silent
  again (``WatchedPlayer``);
- **slow motion, one frame a tick**
  (``test_a_recording_replays_as_a_demo_player_in_slow_motion_one_frame_a_tick``): each tick
  pays twice a frame's time, and the two players share one budget of a frame each, passed from
  one to the other (``most_frames=1``, as a host shares a budget too small for its tiles), so
  every player falls behind and plays every frame in slow motion.

In both, every game a player builds ends matched with the digests of its recording's solo child
replay, frame for frame (each finished game's digest file is read when the player builds the
next: ``WatchedPlayer``), the frame after the fast-forward is the poster frame, and the player's
surface after each tick is the pixels of the same recording replayed alone, at the frame it
stands at (every frame, in the slow-motion run). The progress itself is the test's: the budgets
here run on a fake clock, and on the real one (``clock.measured_seconds``) how far a tile gets in
an Arcade frame depends on the machine, so a recorded Arcade session replays its inputs, never
its tiles' progress frame for frame (the owner's decision 5 in that plan).

A repository test (tests/test_suite_collection.py ``REPOSITORY_TEST_FILES``): it replays our
members' recordings through their console scripts. The tiles, the reference digests and the
silence check (``Tile``, ``play_alone``, ``reference_digests``, ``assert_no_tile_is_heard``) are
in tests/inner_game_tiles.py, which the engine's inner-game tests share and which reads nothing
of the workspace.
"""

from __future__ import annotations

import hashlib
import itertools
import random
from pathlib import Path
from typing import TYPE_CHECKING

import pygame
import pytest
from pydantic import BaseModel, ConfigDict

from glitchygames import events
from glitchygames.audio import reserve_inner_game_channels
from glitchygames.audio.engine import DEFAULT_LIBRARY_CHANNELS, DEFAULT_LIVE_POOL, LEGACY_CHANNELS
from glitchygames.audio.voices import (
    reserve_channels,
)
from glitchygames.demo_player import DemoPlayer, DemoState, poster_frame
from glitchygames.engine_context import current_context, default_context
from glitchygames.replay.audit import read_digest_file
from tests.display_canvas import show_canvas_on_new_display
from tests.inner_game_tiles import (
    DIGEST_OPTION,
    INTERLEAVED_STEPS,
    QUIET,
    FrameCostClock,
    Tile,
    assert_no_inner_game_is_heard,
    assert_no_tile_is_heard,
    heard_channels,
    play_alone,
    recorded_size,
    recording_id,
    reference_digests,
    switch_away_checked,
)
from tests.workspace_goldens import every_golden_and_bundled_demo

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable

    from glitchygames.inner_game import InnerGame
    from glitchygames.replay.pacer import TickBudget

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Every golden, then every bundled demo: (console script, recording)
RECORDINGS = every_golden_and_bundled_demo(project_root=PROJECT_ROOT)
# Eight goldens and eleven bundled demos (tests/workspace_expectations.py)
EXPECTED_RECORDING_COUNT = 19
# The recordings known to diverge inside a tile, by (console script, file name), each with the
# plans/future-work.md entry that says why. None today: Bitmappy's, which read the host's window
# (bugs/2026-11-20-bitmappy-tile-read-the-hosts-window.md), reads its own screen since 2026-11-20
DIVERGES_INSIDE_A_TILE: dict[tuple[str, str], str] = {}
# The recordings known to change the outer game's key repeat inside a tile, each with its entry
CHANGES_THE_OUTER_KEY_REPEAT: dict[tuple[str, str], str] = {
    ('text-input-demo', 'typing.jsonl.gz'): (
        'plans/future-work.md, "A tile changes the outer game\'s key repeat": '
        "pygame.key.set_repeat is SDL's, one per process, and the demo and its input box set it"
    ),
}
# The outer window the tiles run inside: an Arcade's, another size than any recording's
OUTER_WINDOW_SIZE = (1280, 720)
# The outer game's own blocked event types, none the engine's choice (it allows every type but
# SYSWMEVENT): a tile that changed SDL's blocked set would show (row S6)
OUTER_BLOCKED_TYPES = (*events.CONTROLLER_EVENTS, pygame.MOUSEWHEEL)
OUTER_ALLOWED_TYPES = (pygame.SYSWMEVENT,)
# The outer window's caption: an inner game never names the window
OUTER_CAPTION = 'The Arcade (outer game)'
# The tiles a case builds at once at most: its pair, and the tile replayed alone for its pixels
DECLARED_TILES = 3
# Where in its recording the case's tile is heard, in the switched run: from a third of its
# frames to two thirds (of the frames its reference replayed)
HEARD_FROM_FRACTION = 1 / 3
HEARD_UNTIL_FRACTION = 2 / 3
# The recordings that play sounds in their heard frames (plain plays, or voices on a heard set:
# the others play none), so a heard run that heard nothing fails. By recording, not game: one game
# may record both (Zombies Ain't My Neighbors' neighborhood plays sounds, its title none)
PLAYS_SOUNDS = frozenset({
    ('brave-adventurer', 'classic.jsonl.gz'),
    ('brave-adventurer', 'golden-classic.jsonl.gz'),
    ('brave-adventurer', 'golden-papyrus.jsonl.gz'),
    ('brave-adventurer', 'papyrus.jsonl.gz'),
    ('clockwork-keep', 'climb.jsonl.gz'),
    ('clockwork-keep', 'golden.jsonl.gz'),
    ('mr-muncher', 'chase.jsonl.gz'),
    ('mr-muncher', 'golden.jsonl.gz'),
    ('paddleslap', 'golden.jsonl.gz'),
    ('paddleslap', 'rally.jsonl.gz'),
    ('zombies-aint-my-neighbors', 'golden-neighborhood.jsonl.gz'),
    ('zombies-aint-my-neighbors', 'neighborhood_four_kids.jsonl.gz'),
})
# The demo players' tick: an Arcade's frame period at 60 Hz
ARCADE_TICK_SECONDS = 1 / 60
# The elapsed time each tick of the uneven run pays, in Arcade ticks, cycled: none served, one, a
# few at once (a hitch)
UNEVEN_TICKS = (1, 3, 0, 2, 5)
# The slow-motion run's ticks each pay this many Arcade ticks, and run one frame per player
SLOW_MOTION_TICKS = 2
# The seed of the poster stream: an Arcade draws its posters from random_stream('arcade-posters')
POSTER_SEED = 5
# The frames each slice of the poster's fast-forward may run (its budget on the fake clock)
FAST_FORWARD_SLICE_FRAMES = 64
# The games the case's player plays in the uneven run: the fast-forwarded one, and its loop
UNEVEN_RUN_GAMES = 2
# More ticks than any run needs (the longest recording holds 2,313 frames, and every tick runs at
# least one of a player's frames once it is owed): a run that never ends fails instead of hanging
MOST_PLAYER_TICKS = 10_000


@pytest.fixture(autouse=True)
def inner_game_channels() -> None:
    """Partition the mixer as the outer game's engine does and declare the tiles' channels.

    As an Arcade does at startup, before anything plays (``reserve_inner_game_channels``,
    decision 4 of plans/2026-11-13-arcade-4-sound.md): without it no tile can be built.
    """
    reserve_channels(
        live_pool=DEFAULT_LIVE_POOL,
        library_channels=DEFAULT_LIBRARY_CHANNELS,
        legacy_channels=LEGACY_CHANNELS,
    )
    reserve_inner_game_channels(games=DECLARED_TILES)


@pytest.fixture
def outer_window() -> pygame.Surface:
    """Open the outer window at ``OUTER_WINDOW_SIZE``, showing the canvas.

    The harness sets the test display back to its own size after the test.

    Returns:
        The outer window's surface.

    """
    return show_canvas_on_new_display(size=OUTER_WINDOW_SIZE)


@pytest.fixture
def outer_process_state(outer_window: pygame.Surface) -> Generator[OuterProcessState]:
    """Set the outer game's caption and own blocked event types; put back both afterwards.

    Yields:
        The outer window's size and caption and SDL's blocked state for each type set.

    """
    changed_types = (*OUTER_BLOCKED_TYPES, *OUTER_ALLOWED_TYPES)
    caption_before = pygame.display.get_caption()
    before = blocked_states(event_types=changed_types)
    pygame.display.set_caption(OUTER_CAPTION)
    pygame.event.set_blocked(list(OUTER_BLOCKED_TYPES))
    pygame.event.set_allowed(list(OUTER_ALLOWED_TYPES))
    try:
        yield OuterProcessState(
            window_size=outer_window.get_size(),
            caption=pygame.display.get_caption(),
            blocked=blocked_states(event_types=changed_types),
        )
    finally:
        pygame.display.set_caption(*caption_before)
        pygame.event.set_blocked([
            event_type for event_type, was_blocked in before.items() if was_blocked
        ])
        pygame.event.set_allowed([
            event_type for event_type, was_blocked in before.items() if not was_blocked
        ])


@pytest.fixture
def outer_key_repeat() -> Generator[tuple[int, int]]:
    """Read the outer game's key repeat before the test, and put it back afterwards.

    Yields:
        The key repeat before the test: (delay, interval) in milliseconds.

    """
    delay, interval = pygame.key.get_repeat()
    try:
        yield delay, interval
    finally:
        pygame.key.set_repeat(delay, interval)


class OuterProcessState(BaseModel):
    """What the outer game set in the process, which no tile may change (read-only).

    Attributes:
        window_size: The outer window's size.
        caption: The outer window's caption (``pygame.display.get_caption``).
        blocked: SDL's blocked state for each event type the outer game set.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    window_size: tuple[int, int]
    caption: tuple[str, str]
    blocked: dict[int, bool]

    @classmethod
    def now(cls, *, event_types: Iterable[int]) -> OuterProcessState:
        """Read the window's size and caption and SDL's blocked state for each type.

        Args:
            event_types: The types to read.

        Returns:
            The state as it is now.

        """
        window = pygame.display.get_surface()
        assert window is not None
        return cls(
            window_size=window.get_size(),
            caption=pygame.display.get_caption(),
            blocked=blocked_states(event_types=tuple(event_types)),
        )


def blocked_states(*, event_types: tuple[int, ...]) -> dict[int, bool]:
    """Return SDL's blocked state for each event type.

    Args:
        event_types: The types to read.

    Returns:
        Each type's ``pygame.event.get_blocked``.

    """
    return {event_type: pygame.event.get_blocked(event_type) for event_type in event_types}


def assert_the_outer_process_state_is_unchanged(*, expected: OuterProcessState, label: str) -> None:
    """Check the outer window and SDL's blocked event types are as the outer game set them.

    Args:
        expected: What the outer game set.
        label: The recording, for the message.

    """
    now = OuterProcessState.now(event_types=expected.blocked)
    assert now == expected, f'{label} changed the outer process state from {expected} to {now}'


def diverges_inside_a_tile(*, console_script: str, recording: Path) -> bool:
    """Tell whether a recording is one known to diverge inside a tile.

    Args:
        console_script: The console script that replays it.
        recording: The recording.

    Returns:
        True when ``DIVERGES_INSIDE_A_TILE`` lists it.

    """
    return (console_script, recording.name) in DIVERGES_INSIDE_A_TILE


def partner_of(*, index: int) -> tuple[str, Path]:
    """Return the recording paired with ``RECORDINGS[index]``: the next, wrapping around.

    One known to diverge inside a tile is passed over: it would end after its first frame and
    leave the tile to run alone.

    Args:
        index: The tile's index in ``RECORDINGS``.

    Returns:
        The partner's console script and recording.

    """
    candidates = [
        RECORDINGS[(index + offset) % len(RECORDINGS)] for offset in range(1, len(RECORDINGS))
    ]
    partners = [
        (console_script, recording)
        for console_script, recording in candidates
        if not diverges_inside_a_tile(console_script=console_script, recording=recording)
    ]
    assert partners, 'no recording can be a partner'
    return partners[0]


def pair_parameters() -> list[object]:
    """Return one case per recording, as the tile, with its partner.

    Returns:
        ``pytest.param((tile_script, tile), (partner_script, partner))`` for each recording, a
        known divergence marked ``xfail(strict=True)`` with its reason.

    """
    parameters: list[object] = []
    for index, (console_script, recording) in enumerate(RECORDINGS):
        partner_script, partner = partner_of(index=index)
        marks: list[pytest.MarkDecorator] = []
        if diverges_inside_a_tile(console_script=console_script, recording=recording):
            marks.append(
                pytest.mark.xfail(
                    strict=True,
                    raises=AssertionError,
                    reason=DIVERGES_INSIDE_A_TILE[console_script, recording.name],
                )
            )
        parameters.append(
            pytest.param(
                (console_script, recording),
                (partner_script, partner),
                marks=marks,
                id=(
                    f'{recording_id(console_script=console_script, recording=recording)}'
                    f'+{recording_id(console_script=partner_script, recording=partner)}'
                ),
            )
        )
    return parameters


def heard_frames(*, frame_count: int) -> range:
    """Return the frames the case's tile is heard in, in the switched run.

    Args:
        frame_count: The frames its reference replayed.

    Returns:
        From ``HEARD_FROM_FRACTION`` of them (switched audible before that frame runs) up to
        ``HEARD_UNTIL_FRACTION`` (switched silent before that frame runs).

    """
    heard = range(int(frame_count * HEARD_FROM_FRACTION), int(frame_count * HEARD_UNTIL_FRACTION))
    assert 0 < heard.start < heard.stop < frame_count, (frame_count, heard)
    return heard


def play_interleaved(*, tile: Tile, partner: Tile) -> None:
    """Run two tiles to their ends, unevenly interleaved (``INTERLEAVED_STEPS``, cycled).

    After each turn, nothing a tile played sounds while none is heard (``assert_no_tile_is_heard``).

    Args:
        tile: The case's tile.
        partner: Its partner.

    """
    frame_counts = itertools.cycle(INTERLEAVED_STEPS)
    while tile.running or partner.running:
        tile_frames, partner_frames = next(frame_counts)
        tile.run_frames(frame_count=tile_frames)
        assert_no_tile_is_heard(tiles=(tile, partner))
        partner.run_frames(frame_count=partner_frames)
        assert_no_tile_is_heard(tiles=(tile, partner))


def play_pair(
    *,
    cases: tuple[tuple[str, str, Path], ...],
    run: str,
    work_directory: Path,
    heard: range | None,
) -> dict[str, Tile]:
    """Play a case's tile and its partner interleaved to their ends.

    Args:
        cases: (``tile`` or ``partner``, console script, recording) for each.
        run: The run's name (``silent``, ``switched``), for the contexts and digest files.
        work_directory: Where the digest files go.
        heard: The frames the case's tile is heard in; None for a silent run.

    Returns:
        The finished tiles, by ``tile`` and ``partner``.

    """
    tiles = {
        name: Tile(
            console_script=script,
            recording=recording,
            name=f'{run}-{name}',
            work_directory=work_directory,
            heard=heard if name == 'tile' else None,
        )
        for name, script, recording in cases
    }
    play_interleaved(tile=tiles['tile'], partner=tiles['partner'])
    assert current_context() is default_context()
    return tiles


class WatchedPlayer:
    """A ``DemoPlayer`` of a recording with ``--replay-digest``, its games and pixels checked.

    Each game it builds writes the digest file when it ends; the player's ``on_new_game`` reads
    it as the next game is built, so every finished game's digests are kept
    (``finished_digests``). After each tick its surface is checked against the recording replayed
    alone at the frame it stands at (``check_frames``), and the game a tick finished is checked
    at its last frame too.
    """

    def __init__(
        self,
        *,
        console_script: str,
        recording: Path,
        digest_path: Path,
        alone_pixel_hashes: list[str],
        clock: FrameCostClock,
    ) -> None:
        """Make the player (it builds its first game) and watch it with the fake clock.

        Args:
            console_script: The console script that replays the recording.
            recording: The recording.
            digest_path: Where each of its games writes its digests.
            alone_pixel_hashes: The recording's pixels replayed alone, one hash a frame.
            clock: The fake real-time clock its budgets run on.

        """
        self.label = recording_id(console_script=console_script, recording=recording)
        self.digest_path = digest_path
        self.alone_pixel_hashes = alone_pixel_hashes
        # Each finished game's digests and divergence, in the order the games ended
        self.finished_digests: list[tuple[list[str], str | None]] = []
        # By generation, the frames whose pixels were checked, in order
        self.checked_frames: dict[int, list[int]] = {}
        self.games_built = 0
        self.ticks_behind = 0
        self.most_frames_in_a_tick = 0
        self.ticks_with_a_heard_sound = 0
        self.switched_away = False
        self.player = DemoPlayer(
            command=console_script,
            recording=recording,
            nominal_tick_seconds=ARCADE_TICK_SECONDS,
            arguments=(*QUIET, DIGEST_OPTION, str(self.digest_path)),
            on_new_game=self._read_the_last_games_digests,
        )
        clock.players.append(self.player)
        assert self.player.outcome.state is DemoState.PLAYING, (
            f'{self.label}: {self.player.outcome}'
        )

    def _read_the_last_games_digests(self, _inner_game: InnerGame) -> None:
        """Keep the digests the game before this new one wrote at its end (none for the first)."""
        if self.games_built:
            self.finished_digests.append(read_digest_file(path=self.digest_path))
        self.games_built += 1

    def tick(self, *, elapsed_seconds: float, budget: TickBudget, most_frames: int | None = None):
        """Tick the player, then check the pixels of each game the tick ran frames of.

        Args:
            elapsed_seconds: The time the tick pays.
            budget: The tick's budget (possibly shared).
            most_frames: The player's share of a shared budget, or None.

        """
        game_before = self.player.inner_game
        generation_before = self.player.generation
        frame_before = self.player.frame_index

        frames_run = self.player.tick(
            elapsed_seconds=elapsed_seconds, budget=budget, most_frames=most_frames
        )

        self.most_frames_in_a_tick = max(self.most_frames_in_a_tick, frames_run)
        self.ticks_behind += self.player.is_behind
        game = self.player.inner_game
        assert game is not None, self.label
        if game is game_before:
            if game.frame_index > frame_before:
                self.check_frame(game=game, generation=generation_before)
            return
        # The tick ended the game it began with (checked at its last frame) and built another
        if game_before is not None and game_before.frame_index > frame_before:
            self.check_frame(game=game_before, generation=generation_before)
        if game.frame_index > 0:
            self.check_frame(game=game, generation=self.player.generation)

    def check_frame(self, *, game: InnerGame, generation: int) -> None:
        """Check a game's render target is the recording's pixels alone at its last frame run.

        Args:
            game: One of the player's games.
            generation: Which of its games it is (1 for the first).

        """
        frame = game.frame_index - 1
        # The current game's is what a host reads: the player's surface (rule 7)
        surface = self.player.surface if game is self.player.inner_game else game.surface
        assert surface is not None, self.label
        pixels = pygame.image.tobytes(surface, 'RGB')
        assert hashlib.sha256(pixels).hexdigest() == self.alone_pixel_hashes[frame], (
            f'{self.label}, game {generation}: frame {frame} differs from the recording alone'
        )
        self.checked_frames.setdefault(generation, []).append(frame)

    def switch_for_the_heard_frames(self, *, heard: range, generation: int) -> None:
        """Make the player heard from ``heard.start`` and silent from ``heard.stop``, once.

        Only in game ``generation``; the switch silent is checked (``switch_away_checked``).

        Args:
            heard: The frames to be heard in, by the game's next frame.
            generation: The game to be heard in.

        """
        player = self.player
        if player.generation != generation or self.switched_away:
            return
        if not player.audible and player.frame_index >= heard.start:
            player.set_audible(audible=True)
        elif player.audible and player.frame_index >= heard.stop:
            game = player.inner_game
            assert game is not None, self.label
            switch_away_checked(
                label=self.label,
                inner_game=game,
                make_silent=lambda: player.set_audible(audible=False),
            )
            self.switched_away = True

    def count_a_heard_sound(self) -> None:
        """Count the tick when the player is heard and one of its sounds is playing."""
        game = self.player.inner_game
        if self.player.audible and game is not None and heard_channels(inner_game=game):
            self.ticks_with_a_heard_sound += 1

    def assert_each_finished_game_matched(self, *, reference: list[str], games: int) -> None:
        """Check at least ``games`` games ended, each with the reference's digests and matched.

        Args:
            reference: The recording's solo child replay's digests.
            games: How many games must have ended.

        """
        assert len(self.finished_digests) >= games, f'{self.label}: {self.player.outcome}'
        for generation, (digests, divergence) in enumerate(self.finished_digests, start=1):
            assert divergence is None, f'{self.label}, game {generation}: {divergence}'
            assert digests == reference, f'{self.label}, game {generation}: digests differ'

    def assert_each_finished_game_was_checked_in_order(self, *, games: int, frame_count: int):
        """Check each of the first ``games`` games' pixels were checked forwards, to its last frame.

        Args:
            games: How many games ended.
            frame_count: The recording's frames.

        """
        for generation in range(1, games + 1):
            checked = self.checked_frames[generation]
            assert checked == sorted(set(checked)), f'{self.label}, game {generation}: {checked}'
            assert checked[-1] == frame_count - 1, f'{self.label}, game {generation}'


def assert_none_is_heard(*, players: Iterable[WatchedPlayer]) -> None:
    """While no player is audible, check nothing one's current game played sounds.

    Args:
        players: The players.

    """
    assert_no_inner_game_is_heard(
        inner_games={
            watched.label: watched.player.inner_game
            for watched in players
            if watched.player.inner_game is not None
        }
    )


def references_and_alone(
    *,
    cases: tuple[tuple[str, str, Path], ...],
    work_directory: Path,
    outer_process_state: OuterProcessState,
) -> tuple[dict[str, list[str]], dict[str, Tile]]:
    """Replay each recording alone: headless in a child (digests) and as an inner game (pixels).

    After each inner game alone, the outer window and blocked event types are unchanged.

    Args:
        cases: (``tile`` or ``partner``, console script, recording) for each.
        work_directory: Where the digest files go.
        outer_process_state: What the outer game set.

    Returns:
        The reference digests and the finished alone tiles, each by ``tile`` and ``partner``.

    """
    references: dict[str, list[str]] = {}
    alone: dict[str, Tile] = {}
    for name, script, recording in cases:
        references[name] = reference_digests(
            console_script=script, recording=recording, work_directory=work_directory
        )
        alone[name] = play_alone(
            console_script=script, recording=recording, work_directory=work_directory
        )
        assert_the_outer_process_state_is_unchanged(
            expected=outer_process_state, label=alone[name].label
        )
        assert alone[name].matched_digests() == references[name], alone[name].label
    return references, alone


def watched_players(
    *,
    cases: tuple[tuple[str, str, Path], ...],
    run: str,
    work_directory: Path,
    alone: dict[str, Tile],
    clock: FrameCostClock,
) -> dict[str, WatchedPlayer]:
    """Make the case's two demo players, watched by the fake clock.

    Args:
        cases: (``tile`` or ``partner``, console script, recording) for each.
        run: The run's name, for the digest files.
        work_directory: Where the digest files go.
        alone: The recordings replayed alone, for their pixels.
        clock: The fake real-time clock.

    Returns:
        The players, by ``tile`` and ``partner``.

    """
    return {
        name: WatchedPlayer(
            console_script=script,
            recording=recording,
            digest_path=work_directory / f'{run}-player-{name}.digest',
            alone_pixel_hashes=alone[name].pixel_hashes,
            clock=clock,
        )
        for name, script, recording in cases
    }


def fast_forward_to_a_poster(*, watched: WatchedPlayer, clock: FrameCostClock) -> int:
    """Fast-forward a player, in slices, to a poster frame drawn from the seeded stream.

    Args:
        watched: The player, silent.
        clock: The fake real-time clock its slices' budgets run on.

    Returns:
        The poster frame: the player's next frame.

    """
    poster = poster_frame(frame_count=watched.player.frame_count, stream=random.Random(POSTER_SEED))
    slices = 1
    while not watched.player.fast_forward(
        to_frame=poster, budget=clock.budget(frame_count=FAST_FORWARD_SLICE_FRAMES)
    ):
        slices += 1
    assert watched.player.frame_index == poster, watched.label
    # Each slice ran its budget's frames: the fast-forward took as many slices as it needed
    assert slices == max(1, -(-poster // FAST_FORWARD_SLICE_FRAMES)), watched.label
    return poster


def play_unevenly(
    *,
    case_player: WatchedPlayer,
    partner_player: WatchedPlayer,
    clock: FrameCostClock,
    heard: range,
) -> None:
    """Tick two players with uneven time and budgets until the case's has played two games.

    And the partner one. The case's player is heard in ``heard`` of its second game. After each
    player's tick nothing either played sounds while none is heard.

    Args:
        case_player: The case's player.
        partner_player: Its partner.
        clock: The fake real-time clock the budgets run on.
        heard: The frames of the case's second game to hear it in.

    """
    players = (case_player, partner_player)
    elapsed_ticks = itertools.cycle(UNEVEN_TICKS)
    budgets = itertools.cycle(INTERLEAVED_STEPS)
    for _tick in range(MOST_PLAYER_TICKS):
        if (
            len(case_player.finished_digests) >= UNEVEN_RUN_GAMES
            and partner_player.finished_digests
        ):
            return
        elapsed_seconds = next(elapsed_ticks) * ARCADE_TICK_SECONDS
        case_frames, partner_frames = next(budgets)
        case_player.switch_for_the_heard_frames(heard=heard, generation=UNEVEN_RUN_GAMES)
        case_player.tick(
            elapsed_seconds=elapsed_seconds, budget=clock.budget(frame_count=case_frames)
        )
        case_player.count_a_heard_sound()
        assert_none_is_heard(players=players)
        partner_player.tick(
            elapsed_seconds=elapsed_seconds, budget=clock.budget(frame_count=partner_frames)
        )
        assert_none_is_heard(players=players)
    pytest.fail(f'the players did not finish in {MOST_PLAYER_TICKS} ticks')


@pytest.mark.parametrize(('tile', 'partner'), pair_parameters())
def test_a_recording_replays_inside_a_tile_beside_another_as_it_does_alone(
    tile: tuple[str, Path],
    partner: tuple[str, Path],
    tmp_path: Path,
    outer_process_state: OuterProcessState,
    outer_key_repeat: tuple[int, int],
):
    """Interleaved unevenly, each tile matches its solo child replay and draws what it draws alone.

    Twice: with every tile silent, and with the case's tile heard for its middle third (Review
    Focus 2 and 4 of plans/2026-11-13-arcade-4-sound.md). The outer window, its blocked event
    types and key repeat are the fixtures': the window is another size than any tile's, and a
    tile that changes the repeat is put back (its own test checks it). After each recording
    replayed alone the window and blocked types are unchanged.
    """
    assert outer_process_state.window_size == OUTER_WINDOW_SIZE
    assert outer_key_repeat == pygame.key.get_repeat()
    cases = (('tile', *tile), ('partner', *partner))
    references = {
        name: reference_digests(console_script=script, recording=recording, work_directory=tmp_path)
        for name, script, recording in cases
    }

    silent = play_pair(cases=cases, run='silent', work_directory=tmp_path, heard=None)
    switched = play_pair(
        cases=cases,
        run='switched',
        work_directory=tmp_path,
        heard=heard_frames(frame_count=len(references['tile'])),
    )

    for name, script, recording in cases:
        alone = play_alone(console_script=script, recording=recording, work_directory=tmp_path)
        assert_the_outer_process_state_is_unchanged(expected=outer_process_state, label=alone.label)
        alone.matched_digests()
        for run, tiles in (('silent', silent), ('switched', switched)):
            interleaved = tiles[name]
            assert interleaved.matched_digests() == references[name], f'{run}: {interleaved.label}'
            assert interleaved.pixel_hashes == alone.pixel_hashes, (
                f'{run}: {interleaved.label}: its pixels beside another tile differ from its '
                'pixels alone'
            )
    heard_tile = switched['tile']
    assert heard_tile.switched_away, f'{heard_tile.label} was never switched away from'
    # A recording that plays sound was heard while heard: the switched run proves something
    tile_script, tile_recording = tile
    plays_sounds = (tile_script, tile_recording.name) in PLAYS_SOUNDS
    assert (heard_tile.frames_with_a_heard_sound > 0) == plays_sounds, (
        f'{heard_tile.label}: {heard_tile.frames_with_a_heard_sound} heard frames sounding'
    )


@pytest.mark.parametrize(('tile', 'partner'), pair_parameters())
def test_a_recording_replays_as_a_demo_player_beside_another_as_it_does_alone(
    tile: tuple[str, Path],
    partner: tuple[str, Path],
    tmp_path: Path,
    outer_process_state: OuterProcessState,
    outer_key_repeat: tuple[int, int],
):
    """Fast-forwarded to a poster, ticked unevenly, looped and heard: every frame as alone.

    The case's player fast-forwards in slices to a seeded poster frame, and the tick after draws
    it; both players are then ticked with uneven time and budgets until the case's recording has
    looped and played once more, heard for the middle third of that second game. Every game that
    ended matched its solo child replay's digests, every tick's surface is the recording's alone
    at its frame, and nothing either played sounds while none is heard.
    """
    assert outer_key_repeat == pygame.key.get_repeat()
    cases = (('tile', *tile), ('partner', *partner))
    references, alone = references_and_alone(
        cases=cases, work_directory=tmp_path, outer_process_state=outer_process_state
    )
    clock = FrameCostClock()
    players = watched_players(
        cases=cases, run='uneven', work_directory=tmp_path, alone=alone, clock=clock
    )
    case_player, partner_player = players['tile'], players['partner']
    try:
        poster = fast_forward_to_a_poster(watched=case_player, clock=clock)
        play_unevenly(
            case_player=case_player,
            partner_player=partner_player,
            clock=clock,
            heard=heard_frames(frame_count=len(references['tile'])),
        )
    finally:
        for watched in players.values():
            watched.player.finish()

    assert current_context() is default_context()
    assert_the_outer_process_state_is_unchanged(expected=outer_process_state, label='the players')
    case_player.assert_each_finished_game_matched(
        reference=references['tile'], games=UNEVEN_RUN_GAMES
    )
    partner_player.assert_each_finished_game_matched(reference=references['partner'], games=1)
    # The first tick after the fast-forward (a one-frame budget) draws the poster frame
    assert case_player.checked_frames[1][0] == poster, case_player.label
    case_player.assert_each_finished_game_was_checked_in_order(
        games=UNEVEN_RUN_GAMES, frame_count=len(references['tile'])
    )
    partner_player.assert_each_finished_game_was_checked_in_order(
        games=1, frame_count=len(references['partner'])
    )
    assert case_player.switched_away, f'{case_player.label} was never switched away from'
    tile_script, tile_recording = tile
    plays_sounds = (tile_script, tile_recording.name) in PLAYS_SOUNDS
    assert (case_player.ticks_with_a_heard_sound > 0) == plays_sounds, (
        f'{case_player.label}: {case_player.ticks_with_a_heard_sound} heard ticks sounding'
    )


@pytest.mark.parametrize(('tile', 'partner'), pair_parameters())
def test_a_recording_replays_as_a_demo_player_in_slow_motion_one_frame_a_tick(
    tile: tuple[str, Path],
    partner: tuple[str, Path],
    tmp_path: Path,
    outer_process_state: OuterProcessState,
    outer_key_repeat: tuple[int, int],
):
    """Twice a frame's time a tick, one frame each of a shared budget: slow, and every frame shown.

    Both players share one budget of two frames a tick, each taking at most one
    (``most_frames=1``), so they fall behind and play in slow motion; every frame of the first
    game is drawn as the recording alone draws it, in order, and the game ends matched.
    """
    assert outer_key_repeat == pygame.key.get_repeat()
    cases = (('tile', *tile), ('partner', *partner))
    references, alone = references_and_alone(
        cases=cases, work_directory=tmp_path, outer_process_state=outer_process_state
    )
    clock = FrameCostClock()
    players = watched_players(
        cases=cases, run='slow', work_directory=tmp_path, alone=alone, clock=clock
    )
    try:
        for _tick in range(MOST_PLAYER_TICKS):
            if all(watched.finished_digests for watched in players.values()):
                break
            budget = clock.budget(frame_count=len(players))
            for watched in players.values():
                watched.tick(
                    elapsed_seconds=SLOW_MOTION_TICKS * ARCADE_TICK_SECONDS,
                    budget=budget,
                    most_frames=1,
                )
                assert_none_is_heard(players=players.values())
        else:
            pytest.fail(f'the players did not finish in {MOST_PLAYER_TICKS} ticks')
    finally:
        for watched in players.values():
            watched.player.finish()

    assert current_context() is default_context()
    assert_the_outer_process_state_is_unchanged(expected=outer_process_state, label='the players')
    for name, watched in players.items():
        watched.assert_each_finished_game_matched(reference=references[name], games=1)
        assert watched.checked_frames[1] == list(range(len(references[name]))), watched.label
        assert watched.most_frames_in_a_tick == 1, watched.label
        assert watched.ticks_behind > 0, f'{watched.label} never fell behind'


def key_repeat_parameters() -> list[object]:
    """Return one case per recording, a known key-repeat change marked ``xfail(strict=True)``.

    Returns:
        ``pytest.param(console_script, recording)`` for each recording.

    """
    parameters: list[object] = []
    for console_script, recording in RECORDINGS:
        marks: list[pytest.MarkDecorator] = []
        if (console_script, recording.name) in CHANGES_THE_OUTER_KEY_REPEAT:
            marks.append(
                pytest.mark.xfail(
                    strict=True,
                    raises=AssertionError,
                    reason=CHANGES_THE_OUTER_KEY_REPEAT[console_script, recording.name],
                )
            )
        parameters.append(
            pytest.param(
                console_script,
                recording,
                marks=marks,
                id=recording_id(console_script=console_script, recording=recording),
            )
        )
    return parameters


@pytest.mark.parametrize(('console_script', 'recording'), key_repeat_parameters())
def test_a_tile_leaves_the_outer_key_repeat_as_it_was(
    console_script: str,
    recording: Path,
    tmp_path: Path,
    outer_process_state: OuterProcessState,
    outer_key_repeat: tuple[int, int],
):
    """Review Focus 4: a recording replayed to its end as an inner game leaves SDL's key repeat.

    And the outer window's size and caption and SDL's blocked event types (row S6), checked
    first: the strict xfail of a known key-repeat change must fail on the key repeat alone.
    """
    assert outer_process_state.window_size == OUTER_WINDOW_SIZE

    alone = play_alone(console_script=console_script, recording=recording, work_directory=tmp_path)

    assert_the_outer_process_state_is_unchanged(expected=outer_process_state, label=alone.label)
    key_repeat_after = pygame.key.get_repeat()
    assert key_repeat_after == outer_key_repeat, (
        f'{recording_id(console_script=console_script, recording=recording)} changed the outer '
        f'key repeat from {outer_key_repeat} to {key_repeat_after}'
    )


def test_the_recordings_are_every_golden_and_bundled_demo():
    """Nineteen recordings, each known divergence among them: an empty list would prove nothing."""
    names = {(console_script, recording.name) for console_script, recording in RECORDINGS}

    assert len(names) == len(RECORDINGS) == EXPECTED_RECORDING_COUNT
    assert set(DIVERGES_INSIDE_A_TILE) <= names
    assert set(CHANGES_THE_OUTER_KEY_REPEAT) <= names


def test_the_outer_window_is_another_size_than_every_tile():
    """No recording was made at the outer window's width, nor at its height."""
    for console_script, recording in RECORDINGS:
        width, height = recorded_size(recording=recording)

        assert width != OUTER_WINDOW_SIZE[0], (console_script, recording.name)
        assert height != OUTER_WINDOW_SIZE[1], (console_script, recording.name)


def test_a_partner_is_the_next_recording_not_known_to_diverge():
    """Each case's partner follows it, wrapping around, passing over a known divergence."""
    for index in range(len(RECORDINGS)):
        partner_script, partner = partner_of(index=index)
        next_script, next_recording = RECORDINGS[(index + 1) % len(RECORDINGS)]

        assert not diverges_inside_a_tile(console_script=partner_script, recording=partner)
        if not diverges_inside_a_tile(console_script=next_script, recording=next_recording):
            assert (partner_script, partner) == (next_script, next_recording)


def test_every_recording_said_to_play_sounds_exists():
    """``PLAYS_SOUNDS`` names only recordings that exist: a renamed one cannot slip out of it."""
    assert {(console_script, path.name) for console_script, path in RECORDINGS} >= PLAYS_SOUNDS
