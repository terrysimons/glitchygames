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

A repository test (tests/test_suite_collection.py ``REPOSITORY_TEST_FILES``): it replays our
members' recordings through their console scripts.
"""

from __future__ import annotations

import hashlib
import itertools
from pathlib import Path
from typing import TYPE_CHECKING

import pygame
import pytest
from pydantic import BaseModel, ConfigDict

from glitchygames import events
from glitchygames.audio import reserve_inner_game_channels
from glitchygames.audio.engine import DEFAULT_LIBRARY_CHANNELS, DEFAULT_LIVE_POOL, LEGACY_CHANNELS
from glitchygames.audio.voices import (
    DEFAULT_HEARD_SET_CHANNELS,
    INNER_CHANNELS_SLOT,
    heard_set_start,
    plain_play_channel_indices,
    reserve_channels,
    unreserved_channel_indices,
)
from glitchygames.engine_context import current_context, default_context
from glitchygames.exit_codes import ExitCode
from glitchygames.inner_game import InnerGame, InnerGameState
from glitchygames.replay.audit import read_digest_file
from glitchygames.replay.driver import recorded_screen_size
from glitchygames.replay.tools.children import replay_recording_headless
from glitchygames.tracing import TraceReader
from tests.display_canvas import show_canvas_on_new_display
from tests.workspace_goldens import every_golden_and_bundled_demo

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable

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
# How many frames each tile runs in turn, cycled: (the tile's, its partner's). Uneven, so the
# two never run in step, and each sometimes runs several frames while the other waits
INTERLEAVED_STEPS = ((1, 2), (3, 1), (2, 3), (1, 1), (4, 2))
# The inner games' arguments after the replay's own: the tools' quiet log level, as the
# reference child gets (children.headless_replay_arguments)
QUIET = ('--log-level', 'warning')
DIGEST_OPTION = '--replay-digest'
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


def recording_id(*, console_script: str, recording: Path) -> str:
    """Return a recording's name in test ids and messages.

    Args:
        console_script: The console script that replays it.
        recording: The recording.

    Returns:
        ``paddleslap/rally.jsonl.gz``.

    """
    return f'{console_script}/{recording.name}'


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


def recorded_size(*, recording: Path) -> tuple[int, int]:
    """Return the size a recording was made at: its tile's render target.

    Args:
        recording: The recording.

    Returns:
        The header's ``screen_size``.

    """
    with TraceReader(path=recording) as reader:
        size = recorded_screen_size(header=reader.header)
    assert size is not None, f'{recording} records no screen size'
    return size


def reference_digests(*, console_script: str, recording: Path, work_directory: Path) -> list[str]:
    """Replay a recording alone, headless, in a child, and return its frame digests.

    Args:
        console_script: The console script that replays it.
        recording: The recording.
        work_directory: Where the digest file goes.

    Returns:
        One digest per replayed frame.

    """
    digest_path = work_directory / f'{console_script}-{recording.name}.reference.digest'
    child = replay_recording_headless(
        console_script=console_script,
        path=recording,
        game_arguments=(DIGEST_OPTION, str(digest_path)),
    )
    label = recording_id(console_script=console_script, recording=recording)
    assert child.returncode == ExitCode.SUCCESS, f'{label} alone: {child.stdout[-2000:]}'
    digests, divergence = read_digest_file(path=digest_path)
    assert divergence is None, f'{label} alone: {divergence}'
    return digests


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


class Tile:
    """One recording replayed as an ``InnerGame``, hashing its render target after each frame."""

    def __init__(
        self,
        *,
        console_script: str,
        recording: Path,
        name: str,
        work_directory: Path,
        heard: range | None = None,
    ) -> None:
        """Start the recording's replay inside its own context, with a digest file.

        Args:
            console_script: The console script that replays it.
            recording: The recording.
            name: The inner context's name (and the digest file's).
            work_directory: Where the digest file goes.
            heard: The frames the tile is heard in (switched audible before the first runs and
                silent before the stop runs); None to keep it silent.

        """
        self.label = recording_id(console_script=console_script, recording=recording)
        self.digest_path = work_directory / f'{name}.digest'
        self.pixel_hashes: list[str] = []
        self.heard = heard
        # The heard frames whose step left a sound of the tile's playing: a plain play, or a voice
        # on its heard set (heard_channels). Its live chunks are not counted: one switched
        # audible is heard from its next chunk, which comes by real time
        # (glitchygames/audio/live.py), so whether an unpaced tile's heard frames reach it
        # depends on the machine
        self.frames_with_a_heard_sound = 0
        # What the tile had sounding when it was switched away from: plain plays, live chunks
        self.plain_plays_stopped_at_the_switch = 0
        self.live_chunks_muted_at_the_switch = 0
        self.switched_away = False
        self.inner_game = InnerGame.replay(
            command=console_script,
            path=recording,
            name=name,
            size=recorded_size(recording=recording),
            arguments=(*QUIET, DIGEST_OPTION, str(self.digest_path)),
        )
        assert self.running, f'{self.label}: {self.inner_game.outcome}'
        assert not self.inner_game.audible, f'{self.label}: a new inner game is silent'

    @property
    def running(self) -> bool:
        """True until the inner game ends or fails."""
        return self.inner_game.outcome.state is InnerGameState.RUNNING

    def live_pool_chunks(self) -> list[pygame.mixer.Sound]:
        """Return the chunks playing or queued on the tile's live pool.

        Returns:
            Each chunk (none once the tile finished and gave its pool back).

        """
        partition = self.inner_game.context.value(slot=INNER_CHANNELS_SLOT).partition
        if partition is None:
            return []
        chunks: list[pygame.mixer.Sound] = []
        for channel_index in partition.live:
            channel = pygame.mixer.Channel(channel_index)
            chunks.extend(
                chunk for chunk in (channel.get_sound(), channel.get_queue()) if chunk is not None
            )
        return chunks

    def heard_channels(self) -> tuple[int, ...]:
        """Return the channels sounding one of the tile's sounds: plain plays, and its heard set.

        Returns:
            Their indices.

        """
        with self.inner_game.context.active():
            start = heard_set_start()
        heard_set = (
            ()
            if start is None
            else tuple(
                index
                for index in range(start, start + DEFAULT_HEARD_SET_CHANNELS)
                if pygame.mixer.Channel(index).get_busy()
            )
        )
        return (*self.plain_play_channels(), *heard_set)

    def plain_play_channels(self) -> tuple[int, ...]:
        """Return the unreserved channels playing a plain play the tile started (followed).

        Returns:
            Their indices.

        """
        with self.inner_game.context.active():
            return plain_play_channel_indices()

    def switch_away(self) -> None:
        """Make the tile silent: what it had sounding is off the mixer at once (decision 6)."""
        plain_play_channels = self.plain_play_channels()
        audible_chunks = [chunk for chunk in self.live_pool_chunks() if chunk.get_volume() > 0]

        self.inner_game.set_audible(audible=False)

        for channel_index in plain_play_channels:
            channel = pygame.mixer.Channel(channel_index)
            assert not channel.get_busy(), f'{self.label}: channel {channel_index} plays on'
        assert all(chunk.get_volume() == 0 for chunk in audible_chunks), self.label
        self.plain_plays_stopped_at_the_switch = len(plain_play_channels)
        self.live_chunks_muted_at_the_switch = len(audible_chunks)
        self.switched_away = True

    def _switch_before_the_frame(self) -> None:
        """Switch the tile audible or silent when the next frame starts or ends its heard frames."""
        if self.heard is None:
            return
        next_frame = self.inner_game.outcome.frames_run
        if next_frame == self.heard.start:
            self.inner_game.set_audible(audible=True)
        elif next_frame == self.heard.stop:
            self.switch_away()

    def run_frames(self, *, frame_count: int) -> None:
        """Run up to ``frame_count`` frames, hashing the render target after each one that ran.

        Args:
            frame_count: How many frames to run (fewer when the game ends first).

        """
        for _frame in range(frame_count):
            if not self.running:
                return
            self._switch_before_the_frame()
            frames_before = self.inner_game.outcome.frames_run
            self.inner_game.step()
            if self.inner_game.outcome.frames_run > frames_before:
                pixels = pygame.image.tobytes(self.inner_game.surface, 'RGB')
                self.pixel_hashes.append(hashlib.sha256(pixels).hexdigest())
            if self.inner_game.audible and self.heard_channels():
                self.frames_with_a_heard_sound += 1

    def matched_digests(self) -> list[str]:
        """Check the inner game ended matched; return the digests it wrote.

        Returns:
            One digest per replayed frame.

        """
        outcome = self.inner_game.outcome
        assert outcome.state is InnerGameState.ENDED, f'{self.label}: {outcome}'
        assert outcome.diverged is False, f'{self.label}: {outcome.report}'
        digests, divergence = read_digest_file(path=self.digest_path)
        assert divergence is None, f'{self.label}: {divergence}'
        return digests


def play_alone(*, console_script: str, recording: Path, work_directory: Path) -> Tile:
    """Replay a recording as the only inner game, to its end.

    Args:
        console_script: The console script that replays it.
        recording: The recording.
        work_directory: Where its digest file goes.

    Returns:
        The finished tile.

    """
    tile = Tile(
        console_script=console_script,
        recording=recording,
        name=f'alone-{console_script}-{recording.name}',
        work_directory=work_directory,
    )
    while tile.running:
        tile.run_frames(frame_count=1)
    return tile


def assert_no_tile_is_heard(*, tiles: Iterable[Tile]) -> None:
    """While no tile is audible, check nothing a tile played can be heard.

    The outer game plays nothing, so no unreserved channel may play (a silent tile's plain plays
    reach none, a switched-away tile's were stopped), and every chunk on a tile's live pool is
    at volume 0 (its live voices play silent chunks).

    Args:
        tiles: The tiles running.

    """
    tiles = tuple(tiles)
    if any(tile.inner_game.audible for tile in tiles):
        return
    sounding = [
        channel_index
        for channel_index in unreserved_channel_indices()
        if pygame.mixer.Channel(channel_index).get_busy()
    ]
    assert sounding == [], f'unreserved channels {sounding} play while no tile is heard'
    for tile in tiles:
        volumes = [chunk.get_volume() for chunk in tile.live_pool_chunks()]
        assert all(volume == 0 for volume in volumes), f'{tile.label} live chunks at {volumes}'


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


@pytest.mark.heavy_replay(reason='a child-process reference replay beside two inner games')
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


@pytest.mark.heavy_replay(reason='a whole recording replayed as an inner game')
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
