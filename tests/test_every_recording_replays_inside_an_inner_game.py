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

The tiles run inside an outer window of another size than any of them (``OUTER_WINDOW_SIZE``,
an Arcade's): a game that measures the window instead of its own screen is caught, as it would
be in the Arcade. The test display (800x600) is as wide as the 800x480 demos, and hid Bitmappy's
divergence.

The outer game's key repeat (``pygame.key.get_repeat()``: SDL's, one per process) must be the
same after a tile has run (the plan's Review Focus 4: the text-input demo sets its own repeat in
its setup, and the engine's input box another on each key release while it is active). Each
recording is replayed alone as an inner game to check it
(``test_a_tile_leaves_the_outer_key_repeat_as_it_was``); one known to change it
(``CHANGES_THE_OUTER_KEY_REPEAT``) is ``xfail(strict=True)`` with its entry.

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
    from collections.abc import Generator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Every golden, then every bundled demo: (console script, recording)
RECORDINGS = every_golden_and_bundled_demo(project_root=PROJECT_ROOT)
# Six goldens and ten bundled demos (tests/workspace_expectations.py)
EXPECTED_RECORDING_COUNT = 16
# The recordings known to diverge inside a tile, by (console script, file name), each with the
# plans/future-work.md entry that says why
DIVERGES_INSIDE_A_TILE: dict[tuple[str, str], str] = {
    ('bitmappy', 'drawing.jsonl.gz'): (
        'plans/future-work.md, "Bitmappy\'s Arcade tile diverges at frame 0": it sizes its film '
        'strip from pygame.display.get_surface(), the outer window inside a tile'
    ),
}
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
# The report a matched replay starts with (ReplayResult.report)
MATCHED_REPORT_START = 'Replay matched'


@pytest.fixture
def outer_window() -> pygame.Surface:
    """Open the outer window at ``OUTER_WINDOW_SIZE``, showing the canvas.

    The harness sets the test display back to its own size after the test.

    Returns:
        The outer window's surface.

    """
    return show_canvas_on_new_display(size=OUTER_WINDOW_SIZE)


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


class Tile:
    """One recording replayed as an ``InnerGame``, hashing its render target after each frame."""

    def __init__(
        self, *, console_script: str, recording: Path, name: str, work_directory: Path
    ) -> None:
        """Start the recording's replay inside its own context, with a digest file.

        Args:
            console_script: The console script that replays it.
            recording: The recording.
            name: The inner context's name (and the digest file's).
            work_directory: Where the digest file goes.

        """
        self.label = recording_id(console_script=console_script, recording=recording)
        self.digest_path = work_directory / f'{name}.digest'
        self.pixel_hashes: list[str] = []
        self.inner_game = InnerGame.replay(
            command=console_script,
            path=recording,
            name=name,
            size=recorded_size(recording=recording),
            arguments=(*QUIET, DIGEST_OPTION, str(self.digest_path)),
        )
        assert self.running, f'{self.label}: {self.inner_game.outcome}'

    @property
    def running(self) -> bool:
        """True until the inner game ends or fails."""
        return self.inner_game.outcome.state is InnerGameState.RUNNING

    def run_frames(self, *, frame_count: int) -> None:
        """Run up to ``frame_count`` frames, hashing the render target after each one that ran.

        Args:
            frame_count: How many frames to run (fewer when the game ends first).

        """
        for _frame in range(frame_count):
            if not self.running:
                return
            frames_before = self.inner_game.outcome.frames_run
            self.inner_game.step()
            if self.inner_game.outcome.frames_run > frames_before:
                pixels = pygame.image.tobytes(self.inner_game.surface, 'RGB')
                self.pixel_hashes.append(hashlib.sha256(pixels).hexdigest())

    def matched_digests(self) -> list[str]:
        """Check the inner game ended matched; return the digests it wrote.

        Returns:
            One digest per replayed frame.

        """
        outcome = self.inner_game.outcome
        assert outcome.state is InnerGameState.ENDED, f'{self.label}: {outcome}'
        assert outcome.report is not None
        assert outcome.report.startswith(MATCHED_REPORT_START), f'{self.label}: {outcome.report}'
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


def play_interleaved(*, tile: Tile, partner: Tile) -> None:
    """Run two tiles to their ends, unevenly interleaved (``INTERLEAVED_STEPS``, cycled).

    Args:
        tile: The case's tile.
        partner: Its partner.

    """
    frame_counts = itertools.cycle(INTERLEAVED_STEPS)
    while tile.running or partner.running:
        tile_frames, partner_frames = next(frame_counts)
        tile.run_frames(frame_count=tile_frames)
        partner.run_frames(frame_count=partner_frames)


@pytest.mark.parametrize(('tile', 'partner'), pair_parameters())
def test_a_recording_replays_inside_a_tile_beside_another_as_it_does_alone(
    tile: tuple[str, Path],
    partner: tuple[str, Path],
    tmp_path: Path,
    outer_window: pygame.Surface,
    outer_key_repeat: tuple[int, int],
):
    """Interleaved unevenly, each tile matches its solo child replay and draws what it draws alone.

    The outer window and key repeat are the fixtures': the window is another size than any
    tile's, and a tile that changes the repeat is put back (its own test checks it).
    """
    assert outer_window.get_size() == OUTER_WINDOW_SIZE
    assert outer_key_repeat == pygame.key.get_repeat()
    cases = (('tile', *tile), ('partner', *partner))
    references = {
        name: reference_digests(console_script=script, recording=recording, work_directory=tmp_path)
        for name, script, recording in cases
    }

    tiles = {
        name: Tile(console_script=script, recording=recording, name=name, work_directory=tmp_path)
        for name, script, recording in cases
    }
    play_interleaved(tile=tiles['tile'], partner=tiles['partner'])

    assert current_context() is default_context()
    for name, script, recording in cases:
        interleaved = tiles[name]
        assert interleaved.matched_digests() == references[name], interleaved.label
        alone = play_alone(console_script=script, recording=recording, work_directory=tmp_path)
        alone.matched_digests()
        assert interleaved.pixel_hashes == alone.pixel_hashes, (
            f'{interleaved.label}: its pixels beside another tile differ from its pixels alone'
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


@pytest.mark.parametrize(('console_script', 'recording'), key_repeat_parameters())
def test_a_tile_leaves_the_outer_key_repeat_as_it_was(
    console_script: str,
    recording: Path,
    tmp_path: Path,
    outer_window: pygame.Surface,
    outer_key_repeat: tuple[int, int],
):
    """Review Focus 4: a recording replayed to its end as an inner game leaves SDL's key repeat."""
    assert outer_window.get_size() == OUTER_WINDOW_SIZE

    play_alone(console_script=console_script, recording=recording, work_directory=tmp_path)

    key_repeat_after = pygame.key.get_repeat()
    assert key_repeat_after == outer_key_repeat, (
        f'{recording_id(console_script=console_script, recording=recording)} changed the outer '
        f'key repeat from {outer_key_repeat} to {key_repeat_after}'
    )


def test_the_recordings_are_every_golden_and_bundled_demo():
    """Sixteen recordings, each known divergence among them: an empty list would prove nothing."""
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
