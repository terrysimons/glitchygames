"""Recordings replayed as inner games for tests: tiles, their digests, and silence checks.

Shared by the inner-game proof (tests/test_every_recording_replays_inside_an_inner_game.py),
which replays every golden and bundled demo as tiles, and the engine's own inner-game tests
(tests/engine/test_inner_game.py), which replay stand-in games. It names no member and reads
nothing of the workspace, so an engine test may import it (``tests/test_suite_collection.py``:
no engine test reaches ``scripts/``).

- ``Tile``: one recording replayed as an ``InnerGame`` with ``--replay-digest``, hashing its
  render target after each frame it runs, optionally heard for a range of frames.
- ``play_alone``: a recording replayed to its end as the only inner game.
- ``reference_digests``: the recording replayed alone, headless, in a child: one digest a frame.
- ``assert_no_tile_is_heard``: while no tile is audible, nothing a tile played sounds.
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
from glitchygames.replay.tools.children import replay_recording_headless
from glitchygames.tracing import TraceReader

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

# The inner games' arguments after the replay's own: the tools' quiet log level, as the
# reference child gets (children.headless_replay_arguments)
QUIET = ('--log-level', 'warning')
DIGEST_OPTION = '--replay-digest'


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
