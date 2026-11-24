"""Recordings replayed as inner games for tests: tiles, their digests, and silence checks.

Shared by the inner-game proof (tests/test_every_recording_replays_inside_an_inner_game.py),
which replays every golden and bundled demo as tiles, and the engine's own inner-game and demo
player tests (tests/engine/test_inner_game.py, tests/test_demo_player.py), which replay stand-in
games. It names no member and reads nothing of the workspace, so an engine test may import it
(``tests/test_suite_collection.py``: no engine test reaches ``scripts/``).

- ``Tile``: one recording replayed as an ``InnerGame`` with ``--replay-digest``, hashing its
  render target after each frame it runs, optionally heard for a range of frames.
- ``play_alone``: a recording replayed to its end as the only inner game.
- ``reference_digests``: the recording replayed alone, headless, in a child: one digest a frame.
- ``assert_no_tile_is_heard`` (``assert_no_inner_game_is_heard`` for any inner games, a demo
  player's among them): while none is audible, nothing one played sounds.
- ``heard_channels`` and ``switch_away_checked``: what an inner game has sounding, and switching
  it silent with what it had sounding checked off the mixer at once.
- ``FrameCostClock``: a fake real-time clock for demo players' budgets, on which each frame a
  player runs costs ``FRAME_COST_SECONDS``.
- ``INTERLEAVED_STEPS``: how unevenly two tiles are stepped beside each other.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import pygame

from glitchygames.audio.voices import (
    DEFAULT_HEARD_SET_CHANNELS,
    INNER_CHANNELS_SLOT,
    heard_set_start,
    plain_play_channel_indices,
    unreserved_channel_indices,
)
from glitchygames.exit_codes import ExitCode
from glitchygames.inner_game import InnerGame, InnerGameState
from glitchygames.replay.audit import read_digest_file
from glitchygames.replay.driver import recorded_screen_size
from glitchygames.replay.pacer import TickBudget
from glitchygames.replay.tools.children import replay_recording_headless
from glitchygames.tracing import TraceReader

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping
    from pathlib import Path

    from glitchygames.demo_player import DemoPlayer

# The inner games' arguments after the replay's own: the tools' quiet log level, as the
# reference child gets (children.headless_replay_arguments)
QUIET = ('--log-level', 'warning')
DIGEST_OPTION = '--replay-digest'
# How many frames each of two tiles runs in turn, cycled: (the tile's, its partner's). Uneven, so
# the two never run in step, and each sometimes runs several frames while the other waits (the
# inner-game proof's, and the demo player's beside another: tests/test_demo_player.py)
INTERLEAVED_STEPS = ((1, 2), (3, 1), (2, 3), (1, 1), (4, 2))
# Each frame a demo player runs costs this on ``FrameCostClock``: a power of two, so a k-frame
# budget is spent by exactly k frames (tests/engine/test_inner_game.py's frame-cost clock)
FRAME_COST_SECONDS = 1 / 256


def recording_id(*, console_script: str, recording: Path) -> str:
    """Return a recording's name in test ids and messages.

    Args:
        console_script: The console script that replays it.
        recording: The recording.

    Returns:
        ``paddleslap/rally.jsonl.gz``.

    """
    return f'{console_script}/{recording.name}'


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
        return live_pool_chunks(inner_game=self.inner_game)

    def heard_channels(self) -> tuple[int, ...]:
        """Return the channels sounding one of the tile's sounds: plain plays, and its heard set.

        Returns:
            Their indices.

        """
        return heard_channels(inner_game=self.inner_game)

    def plain_play_channels(self) -> tuple[int, ...]:
        """Return the unreserved channels playing a plain play the tile started (followed).

        Returns:
            Their indices.

        """
        return plain_play_channels(inner_game=self.inner_game)

    def switch_away(self) -> None:
        """Make the tile silent: what it had sounding is off the mixer at once (decision 6)."""
        self.plain_plays_stopped_at_the_switch, self.live_chunks_muted_at_the_switch = (
            switch_away_checked(
                label=self.label,
                inner_game=self.inner_game,
                make_silent=lambda: self.inner_game.set_audible(audible=False),
            )
        )
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


def live_pool_chunks(*, inner_game: InnerGame) -> list[pygame.mixer.Sound]:
    """Return the chunks playing or queued on an inner game's live pool.

    Args:
        inner_game: The inner game.

    Returns:
        Each chunk (none once the game finished and gave its pool back).

    """
    partition = inner_game.context.value(slot=INNER_CHANNELS_SLOT).partition
    if partition is None:
        return []
    chunks: list[pygame.mixer.Sound] = []
    for channel_index in partition.live:
        channel = pygame.mixer.Channel(channel_index)
        chunks.extend(
            chunk for chunk in (channel.get_sound(), channel.get_queue()) if chunk is not None
        )
    return chunks


def plain_play_channels(*, inner_game: InnerGame) -> tuple[int, ...]:
    """Return the unreserved channels playing a plain play an inner game started (followed).

    Args:
        inner_game: The inner game.

    Returns:
        Their indices.

    """
    with inner_game.context.active():
        return plain_play_channel_indices()


def heard_channels(*, inner_game: InnerGame) -> tuple[int, ...]:
    """Return the channels sounding one of an inner game's sounds: plain plays, and its heard set.

    Args:
        inner_game: The inner game.

    Returns:
        Their indices.

    """
    with inner_game.context.active():
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
    return (*plain_play_channels(inner_game=inner_game), *heard_set)


def switch_away_checked(
    *, label: str, inner_game: InnerGame, make_silent: Callable[[], None]
) -> tuple[int, int]:
    """Make an inner game silent and check what it had sounding is off the mixer at once.

    Decision 6 of plans/2026-11-13-arcade-4-sound.md: its plain plays stop and its live chunks
    go to volume 0.

    Args:
        label: The recording, for the messages.
        inner_game: The inner game, audible.
        make_silent: What switches it silent (its own ``set_audible``, or its demo player's).

    Returns:
        How many plain plays were stopped and how many live chunks muted.

    """
    plain_plays = plain_play_channels(inner_game=inner_game)
    audible_chunks = [
        chunk for chunk in live_pool_chunks(inner_game=inner_game) if chunk.get_volume() > 0
    ]

    make_silent()

    assert not inner_game.audible, f'{label}: still audible'
    for channel_index in plain_plays:
        channel = pygame.mixer.Channel(channel_index)
        assert not channel.get_busy(), f'{label}: channel {channel_index} plays on'
    assert all(chunk.get_volume() == 0 for chunk in audible_chunks), label
    return len(plain_plays), len(audible_chunks)


def assert_no_tile_is_heard(*, tiles: Iterable[Tile]) -> None:
    """While no tile is audible, check nothing a tile played can be heard.

    Args:
        tiles: The tiles running.

    """
    assert_no_inner_game_is_heard(inner_games={tile.label: tile.inner_game for tile in tiles})


def assert_no_inner_game_is_heard(*, inner_games: Mapping[str, InnerGame]) -> None:
    """While no inner game is audible, check nothing one played can be heard.

    The outer game plays nothing, so no unreserved channel may play (a silent game's plain plays
    reach none, a switched-away game's were stopped), and every chunk on a game's live pool is
    at volume 0 (its live voices play silent chunks).

    Args:
        inner_games: The inner games running, by their labels for the messages.

    """
    if any(inner_game.audible for inner_game in inner_games.values()):
        return
    sounding = [
        channel_index
        for channel_index in unreserved_channel_indices()
        if pygame.mixer.Channel(channel_index).get_busy()
    ]
    assert sounding == [], f'unreserved channels {sounding} play while no inner game is heard'
    for label, inner_game in inner_games.items():
        volumes = [chunk.get_volume() for chunk in live_pool_chunks(inner_game=inner_game)]
        assert all(volume == 0 for volume in volumes), f'{label} live chunks at {volumes}'


class FrameCostClock:
    """A fake real-time clock for demo players' budgets: each frame one runs costs a fixed time.

    Its reading is every watched player's frames played (``DemoPlayer.frames_played``) times
    ``FRAME_COST_SECONDS``, plus what the test charges (``charged_seconds``: a build's cost), so
    a test says how many frames a budget allows.
    """

    def __init__(self) -> None:
        """Watch no player yet, with nothing charged."""
        self.players: list[DemoPlayer] = []
        self.charged_seconds = 0.0

    def __call__(self) -> float:
        """Read the clock.

        Returns:
            Seconds (only differences mean anything).

        """
        frames = sum(player.frames_played for player in self.players)
        return frames * FRAME_COST_SECONDS + self.charged_seconds

    def budget(self, *, frame_count: float) -> TickBudget:
        """Start a budget allowing ``frame_count`` frames, now.

        Args:
            frame_count: How many frames it allows.

        Returns:
            The budget.

        """
        return TickBudget(length_seconds=frame_count * FRAME_COST_SECONDS, measured_seconds=self)

    def charge_frames(self, *, frame_count: int) -> None:
        """Let real time pass as if ``frame_count`` frames ran (a build's cost).

        Args:
            frame_count: How many frames' worth.

        """
        self.charged_seconds += frame_count * FRAME_COST_SECONDS
