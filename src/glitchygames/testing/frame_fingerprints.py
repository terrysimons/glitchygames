"""A pytest plugin that records a fingerprint of every frame each test presents.

PYTEST_DONT_REWRITE: the plugin makes no assertions, and its tests load it into in-process
pytester runs after the suite has imported it (pytest would otherwise warn that it cannot
rewrite an already imported plugin).

It answers one question: does a test draw the same pixels on two SDL video drivers? The dummy
driver and a real one (macOS's cocoa, Linux's x11) draw in software through the same code, and
the engine presents opaque frames (glitchygames/opacity.py), so the same test should present
the same pixels on both; a difference is a driver dependence (BUGS.md #142 was one).
glitchygames/testing/frame_comparison.py (and its command line, scripts/compare_driver_frames.py)
compares the recordings of two or more runs, and
``nox -s compare-drivers`` runs the whole comparison.

It records only when asked (otherwise it registers its markers and runs only the draws_frames
check, below)::

    pytest -p glitchygames.testing.frame_fingerprints --frame-fingerprints DIRECTORY

or with GLITCHYGAMES_FRAME_FINGERPRINTS=DIRECTORY in the environment, with
GLITCHYGAMES_FRAME_FINGERPRINTS_OWNER naming the pytest process it is for (its xdist workers
inherit both; a pytest that a test starts does not record). This project loads the plugin in
every run (the root conftest.py); tests/driver_comparison.py asks it to record when a local run
compares the dummy driver with the native one.

For each test that reaches its call phase it writes one JSON line (``RecordedFrames``) to
``DIRECTORY/<worker>-<pid>.jsonl`` (each xdist worker writes its own file): the test's node id,
its call outcome, a fingerprint (``FrameFingerprint``: size and a SHA-256 of the RGB bytes) of
every frame presented from the start of its setup to the end of its body, in present order, and
of the display as the body left it (the final frame; None without a display), the run's driver
and the final display's, and the test's ``frames_vary`` reason, if marked. A present is a
call of ``pygame.display.flip`` or ``pygame.display.update`` (whose fingerprint is the whole
display, even when only some rectangles were updated). Frames are judged as the window shows
them (``opacity.shown_rgb_bytes``): on a display with per-pixel alpha (cocoa's) alpha 0 shows
black. Presents made outside a test's setup and body (the suite's own canvas, teardown) are not
recorded.

A frame's position is its index in ``RecordedFrames.frames``: the presents, then the final
frame. ``--frame-images-request FILE`` (a ``FrameImageRequest``, written by
glitchygames/testing/frame_comparison.py) also saves the named positions of the named tests as PNG
files, at ``frame_image_path(directory=DIRECTORY, nodeid=..., position=...)``. When it names where
a test may stop (``stop_after_by_test``, a present), the recorder ends that test right after that
present with ``pytest.skip``: its frames are saved, and the rest of the test would only cost time
(a 900-frame test differing at present 20 re-ran in 1.9 s instead of 9.2 s, 2026-11-23). An
outcome exception passes the engine's ``except Exception``, and a skip fails no run; the record
has ``stopped_after`` set and no final frame (its body did not finish).

``--frame-fingerprints-seed SEED`` makes the master seed an engine draws when it is given no
``--random-seed`` depend on SEED and the test's node id alone (``SeededDraws``), so tests that
start engines unseeded draw the same pictures in every run and can be compared; without it they
are nondeterministic by design.

The fingerprint costs about 0.75 ms per present at 800x600 (0.3 ms for the RGB bytes, 0.4 ms for
the hash), plus about 0.3 ms on a display with per-pixel alpha.

The draws_frames marker
-----------------------

A test draws when, from the start of its setup to the end of its body, it presents a frame, or
it leaves the display showing a picture other than the blank screen at the display's size (the
two things a comparison compares; plans/2026-11-22-compare-drivers-only-drawing-tests.md). A
test that draws carries ``@pytest.mark.draws_frames``; a parametrized case marks itself with
``pytest.param(..., marks=pytest.mark.draws_frames)``. ``--draws-frames-only`` runs only the
marked tests (the others are deselected, after any ``-m``): the driver comparison's runs
(``nox -s compare-drivers``, tests/driver_comparison.py's native run) pass it.

The marker cannot go stale: in every run, recording or not, the plugin's check
(``DrawsFramesCheck``) counts each test's presents and compares the display its body left with
the blank screen, then fails a test whose call passed when the marker disagrees: drawing without
it, or marked and drawing nothing. The failure says which, and what to add or remove. A
``frames_vary`` test that draws carries both markers. The blank screen comes from the project's
``pytest_frame_fingerprints_blank_screen(size)`` hook (this suite's: tests/harness.py, the
canvas); without one, only presents count. Each judged run lists its disagreements, one
``<node id><TAB><reason>`` line each, in ``test-results/frame-markers.txt`` (its controller
empties it first); ``--frame-markers-report-only`` lists them without failing any test, and
``uv run python -m scripts.mark_drawing_tests`` places the markers the list asks for.

A run is judged unless a test started it: a pytest that configures while PYTEST_CURRENT_TEST is
set (pytester, in process or as a child process; a tool's run) judges nothing. The run's xdist
workers and tests/driver_comparison.py's native run start outside any test, so they are judged.
The check costs about 0.4 ms per test that presents nothing (one read of the display at
800x600 and a compare), about 13 s of CPU over the whole suite.
"""

from __future__ import annotations

import functools
import hashlib
import os
import re
import types
from pathlib import Path
from typing import TYPE_CHECKING

import pygame
import pytest
from pydantic import BaseModel, ConfigDict, Field

from glitchygames import randomness
from glitchygames.opacity import shown_rgb_bytes

if TYPE_CHECKING:
    from collections.abc import Callable, Generator


FINGERPRINTS_OPTION = '--frame-fingerprints'
IMAGES_REQUEST_OPTION = '--frame-images-request'
SEED_OPTION = '--frame-fingerprints-seed'
# The options' environment variables: a run started with them set (each xdist worker inherits
# its controller's environment) records as if given the options; an option given wins
FINGERPRINTS_VARIABLE = 'GLITCHYGAMES_FRAME_FINGERPRINTS'
SEED_VARIABLE = 'GLITCHYGAMES_FRAME_FINGERPRINTS_SEED'
# The process id of the pytest run the variables are for: they apply in that process and its
# xdist workers (its direct children), never in a pytest a test starts (pytester, replays)
OWNER_VARIABLE = 'GLITCHYGAMES_FRAME_FINGERPRINTS_OWNER'
SDL_VIDEO_DRIVER_VARIABLE = 'SDL_VIDEODRIVER'
# Marks a test whose frames are not expected to match between runs or drivers
FRAMES_VARY_MARKER = 'frames_vary'
# Marks a test that draws: it presents a frame, or leaves a picture other than the blank screen
# (the draws_frames check enforces it both ways; the driver comparison runs only these tests)
DRAWS_FRAMES_MARKER = 'draws_frames'
REPORT_ONLY_OPTION = '--frame-markers-report-only'
# Runs only the tests marked draws_frames (the driver comparison's runs): the others are
# deselected, after any -m selection, so a user's own -m still narrows the run
DRAWS_FRAMES_ONLY_OPTION = '--draws-frames-only'
# Where each judged run writes the tests whose draws_frames marker disagrees with what they did
# (from the run's root directory; the run's controller empties it at the start)
MARKERS_REPORT_PATH = Path('test-results') / 'frame-markers.txt'
# pytest sets this while a test runs: a pytest that configures with it set was started by a
# test (pytester, a replay tool's run), and its tests are not judged
CURRENT_TEST_VARIABLE = 'PYTEST_CURRENT_TEST'
# The draws_frames check's plugin object's name in pytest's plugin manager
CHECK_PLUGIN_NAME = 'draws-frames-check'
RECORDS_SUFFIX = '.jsonl'
IMAGES_DIRECTORY_NAME = 'images'
# The plugin object's name in pytest's plugin manager
RECORDER_PLUGIN_NAME = 'frame-fingerprint-recorder'
# The worker id xdist gives each worker process; a run without xdist is one 'main' process
XDIST_WORKER_VARIABLE = 'PYTEST_XDIST_WORKER'
MAIN_PROCESS_NAME = 'main'
# Hex digits of SHA-256 kept per frame (128 bits)
DIGEST_HEX_LENGTH = 32
# A test's image folder: its node id with anything but these characters replaced, cut to this
# length, then a hash of the whole node id (two node ids can sanitize alike)
UNSAFE_PATH_CHARACTERS = re.compile(r'[^A-Za-z0-9._-]+')
IMAGES_FOLDER_NAME_LENGTH = 100
IMAGES_FOLDER_HASH_LENGTH = 12

# The most bits SeededDraws draws at once: one SHA-256 digest
SEEDED_DRAW_MAXIMUM_BITS = 256

# The real display functions, captured when the plugin is imported (before any test patches
# them); the recorder reads the display through them
_REAL_DISPLAY_GET_SURFACE = pygame.display.get_surface


class FrameFingerprint(BaseModel):
    """One frame as the window shows it: its size and a hash of its RGB bytes."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    width: int
    height: int
    digest: str


class RecordedFrames(BaseModel):
    """What one test presented: one line of a fingerprints file."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    nodeid: str
    # The call phase's outcome: 'passed', 'failed' or 'skipped'
    outcome: str
    presented: tuple[FrameFingerprint | None, ...]
    # The display as the test body left it; None when there was no display
    final: FrameFingerprint | None
    # The SDL video driver the run was on (SDL_VIDEODRIVER) and the one the final frame's
    # display was on (None without a display): a test that runs an engine with --headless
    # moves a real-driver run's display to dummy until the harness moves it back after the test
    run_driver: str | None = None
    final_driver: str | None = None
    # The test's frames_vary marker reason: its frames are not expected to match between runs
    # or drivers, so a comparison lists it instead of comparing it
    frames_vary_reason: str | None = None
    # The present a re-run stopped the test after (FrameImageRequest.stop_after_by_test): its
    # body did not finish, so it has no final frame and its outcome is 'skipped'
    stopped_after: int | None = None

    @property
    def final_on_run_driver(self) -> bool:
        """Tell whether the final frame was drawn on the run's own driver (so it compares).

        Returns:
            True when there was a final display and it was on the run's driver (any driver,
            when the run's is unknown).

        """
        if self.final is None:
            return False
        return self.run_driver is None or self.final_driver == self.run_driver

    @property
    def frames(self) -> tuple[FrameFingerprint | None, ...]:
        """The frames by position: every present, then the final frame.

        Returns:
            The presented frames followed by the final one.

        """
        return (*self.presented, self.final)


class FrameImageRequest(BaseModel):
    """The frames to save as PNG files: positions (in ``RecordedFrames.frames``) by node id.

    ``stop_after_by_test`` names, for some tests, the present after which the re-run may end
    the test (as a skip): every frame it saves is a present at or before that one, so the rest
    of the test would only cost time.
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    positions_by_test: dict[str, tuple[int, ...]]
    stop_after_by_test: dict[str, int] = Field(default_factory=dict)


def frame_position_name(*, position: int, frame_count: int) -> str:
    """Name a frame position for a report: ``present N`` or ``the final frame``.

    Args:
        position: The position in ``RecordedFrames.frames``.
        frame_count: How many frames the record has (the final frame is the last).

    Returns:
        The position's name.

    """
    if position == frame_count - 1:
        return 'the final frame'
    return f'present {position}'


def images_folder_name(*, nodeid: str) -> str:
    """Return the folder name a test's images go in: readable, unique, safe on every OS.

    Args:
        nodeid: The test's node id.

    Returns:
        The node id with unsafe characters replaced, shortened, plus a hash of the node id.

    """
    readable = UNSAFE_PATH_CHARACTERS.sub('_', nodeid)[:IMAGES_FOLDER_NAME_LENGTH]
    node_hash = hashlib.sha256(nodeid.encode()).hexdigest()[:IMAGES_FOLDER_HASH_LENGTH]
    return f'{readable}-{node_hash}'


def frame_image_path(*, directory: Path, nodeid: str, position: int) -> Path:
    """Return where a requested frame's PNG is saved.

    Args:
        directory: The run's fingerprints directory.
        nodeid: The test's node id.
        position: The frame's position in ``RecordedFrames.frames``.

    Returns:
        ``directory/images/<test folder>/frame-<position>.png``.

    """
    test_folder = directory / IMAGES_DIRECTORY_NAME / images_folder_name(nodeid=nodeid)
    return test_folder / f'frame-{position}.png'


def read_recorded_frames(*, directory: Path) -> dict[str, RecordedFrames]:
    """Read every test's record from a run's fingerprints directory.

    Args:
        directory: The directory the run wrote its ``*.jsonl`` files to.

    Returns:
        The records by node id. A node id recorded twice keeps its last record.

    Raises:
        FileNotFoundError: If the directory does not exist (pydantic's ValidationError, a
            ValueError, propagates for a line that is not a record).

    """
    if not directory.is_dir():
        message = f'{directory}: no such fingerprints directory'
        raise FileNotFoundError(message)
    records: dict[str, RecordedFrames] = {}
    for path in sorted(directory.glob(f'*{RECORDS_SUFFIX}')):
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.strip():
                record = RecordedFrames.model_validate_json(line)
                records[record.nodeid] = record
    return records


def fingerprint_display() -> tuple[FrameFingerprint, bytes] | None:
    """Fingerprint the display as the window shows it.

    Returns:
        The fingerprint and the shown RGB bytes, or None when pygame or its display is not
        running, or the display cannot be read (an OpenGL display).

    """
    if not pygame.get_init():
        return None
    try:
        display_surface = _REAL_DISPLAY_GET_SURFACE()
        if not isinstance(display_surface, pygame.Surface):
            return None
        rgb_bytes = shown_rgb_bytes(surface=display_surface)
    except pygame.error:
        return None
    width, height = display_surface.get_size()
    digest = hashlib.sha256(rgb_bytes).hexdigest()[:DIGEST_HEX_LENGTH]
    return FrameFingerprint(width=width, height=height, digest=digest), rgb_bytes


def display_driver() -> str | None:
    """Return the video driver of the running display, if any.

    Returns:
        ``pygame.display.get_driver()``, or None when pygame's display is not running.

    """
    if not pygame.get_init() or not pygame.display.get_init():
        return None
    return pygame.display.get_driver()


def save_frame_image(*, path: Path, fingerprint: FrameFingerprint, rgb_bytes: bytes) -> None:
    """Save a frame's shown RGB bytes as a PNG file (its folders made as needed).

    Args:
        path: The PNG file.
        fingerprint: The frame's fingerprint (for its size).
        rgb_bytes: The frame's shown RGB bytes.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    image = pygame.image.frombytes(rgb_bytes, (fingerprint.width, fingerprint.height), 'RGB')
    pygame.image.save(image, str(path))


class SeededDraws:
    """``secrets.randbits`` made repeatable: draws derived from a key and a draw counter.

    Draw N is the top bits of the SHA-256 of ``<key>:<N>``, so the same key gives the same
    sequence in every process.
    """

    def __init__(self, *, key: str) -> None:
        """Start a sequence.

        Args:
            key: What the sequence depends on.

        """
        self.key = key
        self.draw_count = 0

    def randbits(self, bits: int) -> int:
        """Draw a non-negative integer of ``bits`` random bits, like ``secrets.randbits``.

        Args:
            bits: How many bits (at most 256).

        Returns:
            The next integer of the sequence.

        Raises:
            ValueError: If more than 256 bits are asked for.

        """
        if not 0 <= bits <= SEEDED_DRAW_MAXIMUM_BITS:
            message = f'SeededDraws draws 0 to {SEEDED_DRAW_MAXIMUM_BITS} bits, not {bits}'
            raise ValueError(message)
        digest = hashlib.sha256(f'{self.key}:{self.draw_count}'.encode()).digest()
        self.draw_count += 1
        return int.from_bytes(digest) >> (SEEDED_DRAW_MAXIMUM_BITS - bits)


class FrameFingerprintRecorder:
    """The plugin object: wraps the display's present functions and writes each test's frames.

    Registered by ``pytest_configure`` when ``--frame-fingerprints`` is given; its hooks run in
    the process that runs the tests (each xdist worker).
    """

    def __init__(
        self,
        *,
        directory: Path,
        image_request: FrameImageRequest | None,
        seed: int | None = None,
    ) -> None:
        """Prepare to record into a directory.

        Args:
            directory: Where the records (and requested images) go; made if missing.
            image_request: The frames to save as PNG files, or None for none.
            seed: Seeds each test's unseeded engine runs (``seeded_master_seed_draws``), or
                None to leave them drawing from ``secrets``.

        """
        self.directory = directory
        self.seed = seed
        self.run_driver = os.environ.get(SDL_VIDEO_DRIVER_VARIABLE)
        # The driver of the display the current test's body left (None without a display)
        self.final_driver: str | None = None
        # Replaces the master seed draws for one test (undone before the next one's setup)
        self.seed_patches = pytest.MonkeyPatch()
        self.image_request = image_request or FrameImageRequest(positions_by_test={})
        worker = os.environ.get(XDIST_WORKER_VARIABLE, MAIN_PROCESS_NAME)
        self.records_path = directory / f'{worker}-{os.getpid()}{RECORDS_SUFFIX}'
        # The test being recorded and its presents so far; None between tests
        self.current_nodeid: str | None = None
        self.presented: list[FrameFingerprint | None] = []
        # The display as the current test's body left it (fingerprint and RGB bytes)
        self.final: tuple[FrameFingerprint, bytes] | None = None
        # The present the current test was stopped after (the request's stop), or None
        self.stopped_after: int | None = None
        # Replaces the display's present functions, and puts them back (pytest's own patcher)
        self.display_patches = pytest.MonkeyPatch()
        directory.mkdir(parents=True, exist_ok=True)

    def install(self) -> None:
        """Replace ``pygame.display.flip`` and ``update`` with recording wrappers."""
        self.display_patches.setattr(
            pygame.display, 'flip', self.recording_present(present=pygame.display.flip)
        )
        self.display_patches.setattr(
            pygame.display, 'update', self.recording_present(present=pygame.display.update)
        )

    def uninstall(self) -> None:
        """Put back the display's own present functions and the master seed draws."""
        self.display_patches.undo()
        self.seed_patches.undo()

    def seed_master_seed_draws(self, *, nodeid: str) -> None:
        """Make the master seeds a test's unseeded engine runs draw depend on the test alone.

        An engine started without ``--random-seed`` draws its master seed from
        ``secrets.randbits`` (glitchygames/randomness.py), so such a test draws different
        pictures in every run and could never be compared across drivers. With a seed, those
        draws come from ``SeededDraws`` keyed by the seed and the test's node id: the same
        sequence in every run, different per test. Nothing happens without a seed.

        Args:
            nodeid: The test's node id.

        """
        self.seed_patches.undo()
        if self.seed is None:
            return
        test_draws = SeededDraws(key=f'{self.seed}:{nodeid}')
        self.seed_patches.setattr(
            randomness, 'secrets', types.SimpleNamespace(randbits=test_draws.randbits)
        )

    def recording_present[**PresentParameters](
        self, *, present: Callable[PresentParameters, None]
    ) -> Callable[PresentParameters, None]:
        """Wrap a present function so each present during a test is fingerprinted.

        The frame is fingerprinted before the present (it is what the present shows) and
        recorded after it succeeds.

        Args:
            present: ``pygame.display.flip`` or ``pygame.display.update``.

        Returns:
            The wrapper.

        """

        @functools.wraps(present)
        def present_and_record(
            *args: PresentParameters.args, **kwargs: PresentParameters.kwargs
        ) -> None:
            nodeid = self.current_nodeid
            if nodeid is None or self.stopped_after is not None:
                present(*args, **kwargs)
                return
            shown = fingerprint_display()
            present(*args, **kwargs)
            position = len(self.presented)
            self.record_frame(nodeid=nodeid, shown=shown, position=position)
            self.presented.append(None if shown is None else shown[0])
            if self.image_request.stop_after_by_test.get(nodeid) == position:
                self.stopped_after = position
                # A skip, not an error: pytest's outcome exceptions are BaseExceptions, so the
                # engine's (and a test's) except Exception lets it through, and a skipped test
                # fails no run
                pytest.skip(f'its requested frames were saved by present {position}')

        return present_and_record

    def record_frame(
        self, *, nodeid: str, shown: tuple[FrameFingerprint, bytes] | None, position: int
    ) -> None:
        """Save a frame's image when the request names its position in the test.

        Args:
            nodeid: The test's node id.
            shown: The frame's fingerprint and RGB bytes, or None (nothing to save).
            position: The frame's position in the test's frames.

        """
        if shown is None:
            return
        if position in self.image_request.positions_by_test.get(nodeid, ()):
            fingerprint, rgb_bytes = shown
            save_frame_image(
                path=frame_image_path(directory=self.directory, nodeid=nodeid, position=position),
                fingerprint=fingerprint,
                rgb_bytes=rgb_bytes,
            )

    @pytest.hookimpl(wrapper=True, tryfirst=True)
    def pytest_runtest_setup(self, item: pytest.Item) -> Generator[None]:
        """Start recording a test: its setup's presents count as its frames.

        The master seed draws are seeded for the test first, so its fixtures' engines draw
        them too.

        Args:
            item: The test.

        Returns:
            The setup's result.

        Yields:
            To the setup.

        """
        self.current_nodeid = item.nodeid
        self.presented = []
        self.final = None
        self.final_driver = None
        self.stopped_after = None
        self.seed_master_seed_draws(nodeid=item.nodeid)
        return (yield)

    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_call(self, item: pytest.Item) -> Generator[None]:
        """Run the test body, then fingerprint the display as the body left it.

        Args:
            item: The test.

        Returns:
            The body's result.

        Yields:
            To the body.

        """
        try:
            return (yield)
        finally:
            # A stopped test's body did not finish: what it shows is not its final frame
            if self.stopped_after is None:
                self.final = fingerprint_display()
                self.final_driver = display_driver()
                self.record_frame(
                    nodeid=item.nodeid, shown=self.final, position=len(self.presented)
                )

    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_makereport(
        self, item: pytest.Item, call: pytest.CallInfo[None]
    ) -> Generator[None, pytest.TestReport, pytest.TestReport]:
        """Write the test's record once its call phase is reported, and stop recording it.

        Args:
            item: The test.
            call: The phase being reported.

        Returns:
            The report.

        Yields:
            To the report's making.

        """
        report = yield
        if call.when == 'call':
            frames_vary = item.get_closest_marker(FRAMES_VARY_MARKER)
            record = RecordedFrames(
                nodeid=item.nodeid,
                outcome=report.outcome,
                presented=tuple(self.presented),
                final=None if self.final is None else self.final[0],
                run_driver=self.run_driver,
                final_driver=self.final_driver,
                frames_vary_reason=(
                    None if frames_vary is None else str(frames_vary.kwargs.get('reason', ''))
                ),
                stopped_after=self.stopped_after,
            )
            with self.records_path.open('a', encoding='utf-8') as records_file:
                records_file.write(record.model_dump_json() + '\n')
            self.current_nodeid = None
            self.presented = []
        return report


class FrameFingerprintsHookSpecifications:
    """The hook the plugin asks the project's conftest for: its blank screen."""

    @pytest.hookspec(firstresult=True)
    def pytest_frame_fingerprints_blank_screen(self, size: tuple[int, int]) -> bytes | None:
        """Return the shown RGB bytes a test leaves on a display of this size when it draws nothing.

        A project whose tests start on a known picture (this suite's canvas,
        tests/display_canvas.py) implements it in its root conftest; without an implementation
        only presents count as drawing.

        Args:
            size: The display's width and height.

        Returns:
            The bytes (as ``opacity.shown_rgb_bytes`` reads them), or None when unknown.

        """


class DrawsFramesCheck:
    """The plugin object that keeps the ``draws_frames`` marker true: see the module docstring.

    It counts each test's presents from the start of its setup to the end of its body (through
    wrappers on ``pygame.display.flip`` and ``update``), compares the display the body left with
    the blank screen at its size, and, for a test whose call passed, fails it (or, report-only,
    lists it) when the marker disagrees with what it did.
    """

    def __init__(self, *, config: pytest.Config, report_only: bool) -> None:
        """Prepare to judge a run's tests.

        Args:
            config: pytest's configuration (for the blank-screen hook and the root directory).
            report_only: List disagreements in the report without failing the tests.

        """
        self.config = config
        self.report_only = report_only
        self.report_path = config.rootpath / MARKERS_REPORT_PATH
        # The blank screen's bytes by display size, asked of the hook once per size
        self.blank_screens: dict[tuple[int, int], bytes | None] = {}
        # The test being judged and its presents so far; None between tests
        self.current_nodeid: str | None = None
        self.present_count = 0
        # Whether the display the current test's body left differs from the blank screen
        self.final_differs = False
        self.display_patches = pytest.MonkeyPatch()

    def install(self) -> None:
        """Replace ``pygame.display.flip`` and ``update`` with counting wrappers."""
        self.display_patches.setattr(
            pygame.display, 'flip', self.counting_present(present=pygame.display.flip)
        )
        self.display_patches.setattr(
            pygame.display, 'update', self.counting_present(present=pygame.display.update)
        )

    def uninstall(self) -> None:
        """Put back the present functions the check found."""
        self.display_patches.undo()

    def counting_present[**PresentParameters](
        self, *, present: Callable[PresentParameters, None]
    ) -> Callable[PresentParameters, None]:
        """Wrap a present function so each present during a test is counted.

        Args:
            present: ``pygame.display.flip`` or ``pygame.display.update``.

        Returns:
            The wrapper.

        """

        @functools.wraps(present)
        def present_and_count(
            *args: PresentParameters.args, **kwargs: PresentParameters.kwargs
        ) -> None:
            present(*args, **kwargs)
            if self.current_nodeid is not None:
                self.present_count += 1

        return present_and_count

    def blank_screen(self, *, size: tuple[int, int]) -> bytes | None:
        """Return the blank screen at a size, from the project's hook (asked once per size).

        Args:
            size: The display's width and height.

        Returns:
            The blank screen's shown RGB bytes, or None when the project does not say.

        """
        if size not in self.blank_screens:
            self.blank_screens[size] = self.config.hook.pytest_frame_fingerprints_blank_screen(
                size=size
            )
        return self.blank_screens[size]

    def display_differs_from_the_blank_screen(self) -> bool:
        """Tell whether the display shows a picture other than the blank screen at its size.

        Returns:
            False without a readable display (pygame stopped, no display mode set, an OpenGL
            display) or a known blank screen at its size.

        """
        try:
            display_surface = _REAL_DISPLAY_GET_SURFACE()
            if not isinstance(display_surface, pygame.Surface):
                return False
            blank = self.blank_screen(size=display_surface.get_size())
            if blank is None:
                return False
            return shown_rgb_bytes(surface=display_surface) != blank
        except pygame.error:
            return False

    def disagreement(self, *, item: pytest.Item) -> str | None:
        """Say how the test's draws_frames marker disagrees with what it did, if it does.

        Args:
            item: The test, its call just finished.

        Returns:
            The reason, or None when the marker is right.

        """
        marked = item.get_closest_marker(DRAWS_FRAMES_MARKER) is not None
        if self.present_count:
            drew = f'presented {self.present_count} frame(s)'
        elif self.final_differs:
            drew = 'left a picture other than the blank screen'
        else:
            drew = None
        if drew is not None and not marked:
            return (
                f'draws without the {DRAWS_FRAMES_MARKER} marker ({drew}): add '
                f'@pytest.mark.{DRAWS_FRAMES_MARKER} (a parametrized case: '
                f'pytest.param(..., marks=pytest.mark.{DRAWS_FRAMES_MARKER}))'
            )
        if drew is None and marked:
            return (
                f'is marked {DRAWS_FRAMES_MARKER} but draws nothing (no present, and it leaves '
                f'the blank screen): remove the marker'
            )
        return None

    @pytest.hookimpl(tryfirst=True)
    def pytest_sessionstart(self) -> None:
        """Empty the report at the start of the run (its controller's; workers append).

        An xdist worker is told by its configuration (``workerinput``), not by the
        environment: a pytest a worker's test runs in process inherits the worker's variables.
        """
        if hasattr(self.config, 'workerinput'):
            return
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text('', encoding='utf-8')

    @pytest.hookimpl(wrapper=True, tryfirst=True)
    def pytest_runtest_setup(self, item: pytest.Item) -> Generator[None]:
        """Start counting a test's presents: its setup's count as its own.

        Args:
            item: The test.

        Returns:
            The setup's result.

        Yields:
            To the setup.

        """
        self.current_nodeid = item.nodeid
        self.present_count = 0
        self.final_differs = False
        return (yield)

    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_call(self) -> Generator[None]:
        """Run the test body, then compare the display it left with the blank screen.

        Only a test that presented nothing needs the comparison: a present already draws.

        Returns:
            The body's result.

        Yields:
            To the body.

        """
        try:
            return (yield)
        finally:
            if not self.present_count:
                self.final_differs = self.display_differs_from_the_blank_screen()

    @pytest.hookimpl(wrapper=True)
    def pytest_runtest_makereport(
        self, item: pytest.Item, call: pytest.CallInfo[None]
    ) -> Generator[None, pytest.TestReport, pytest.TestReport]:
        """Judge a test whose call passed, and stop counting it.

        Args:
            item: The test.
            call: The phase being reported.

        Returns:
            The report: failed, with the reason, when the marker disagrees (unless report-only).

        Yields:
            To the report's making.

        """
        report = yield
        if call.when != 'call':
            return report
        self.current_nodeid = None
        if not report.passed:
            return report
        reason = self.disagreement(item=item)
        if reason is None:
            return report
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        with self.report_path.open('a', encoding='utf-8') as report_file:
            report_file.write(f'{item.nodeid}\t{reason}\n')
        if not self.report_only:
            report.outcome = 'failed'
            report.longrepr = f'{item.nodeid} {reason}'
        return report


def pytest_addhooks(pluginmanager: pytest.PytestPluginManager) -> None:
    """Add the blank-screen hook a project's conftest may implement.

    Args:
        pluginmanager: pytest's plugin manager.

    """
    pluginmanager.add_hookspecs(FrameFingerprintsHookSpecifications)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add the plugin's options.

    Args:
        parser: pytest's option parser.

    """
    group = parser.getgroup('frame fingerprints', 'record every presented frame (driver diffs)')
    group.addoption(
        FINGERPRINTS_OPTION,
        metavar='DIRECTORY',
        type=Path,
        default=None,
        help='write a fingerprint of every frame each test presents to DIRECTORY (JSON lines)',
    )
    group.addoption(
        IMAGES_REQUEST_OPTION,
        metavar='FILE',
        type=Path,
        default=None,
        help='also save the frames FILE names (a FrameImageRequest) as PNG files',
    )
    group.addoption(
        SEED_OPTION,
        metavar='SEED',
        type=int,
        default=None,
        help=(
            "seed each test's unseeded engine master seeds from SEED and its node id, so "
            'they are the same in every run'
        ),
    )
    group.addoption(
        DRAWS_FRAMES_ONLY_OPTION,
        action='store_true',
        default=False,
        help=(
            f'run only the tests marked {DRAWS_FRAMES_MARKER} (deselect the rest): the tests '
            'whose frames a driver comparison compares'
        ),
    )
    group.addoption(
        REPORT_ONLY_OPTION,
        action='store_true',
        default=False,
        help=(
            f'list the tests whose {DRAWS_FRAMES_MARKER} marker disagrees with what they did in '
            f'{MARKERS_REPORT_PATH} without failing them (for marking tests in bulk)'
        ),
    )


def environment_applies() -> bool:
    """Tell whether the recording variables are meant for this process.

    Returns:
        True when GLITCHYGAMES_FRAME_FINGERPRINTS_OWNER names this process or its parent (an
        xdist worker's controller).

    """
    owner = os.environ.get(OWNER_VARIABLE, '')
    return owner in {str(os.getpid()), str(os.getppid())}


def judges_this_run(*, config: pytest.Config) -> bool:
    """Tell whether this pytest's tests are judged by the draws_frames check.

    Args:
        config: pytest's configuration.

    Returns:
        True unless a test started this pytest (it configures while a test runs: pytester, a
        tool's run), or it only collects (``--collect-only`` runs no test, and must not empty
        the report a tool may be reading). The run's xdist workers start before any test, so
        they are judged.

    """
    return not os.environ.get(CURRENT_TEST_VARIABLE) and not config.option.collectonly


def pytest_configure(config: pytest.Config) -> None:
    """Register the markers; install the draws_frames check, and the recorder when asked.

    The check is installed in every run a test did not start (``judges_this_run``). Recording
    is asked for by ``--frame-fingerprints`` (or GLITCHYGAMES_FRAME_FINGERPRINTS);
    the seed by ``--frame-fingerprints-seed`` (or GLITCHYGAMES_FRAME_FINGERPRINTS_SEED).

    Args:
        config: pytest's configuration.

    Raises:
        pytest.UsageError: If ``--frame-images-request`` is given without
            ``--frame-fingerprints``, or its file cannot be read.

    """
    config.addinivalue_line(
        'markers',
        f"{FRAMES_VARY_MARKER}(reason): the test's frames are not expected to match between runs "
        'or SDL drivers (nondeterministic, or driver-dependent by design), so the driver '
        'comparison lists it instead of comparing it',
    )
    config.addinivalue_line(
        'markers',
        f'{DRAWS_FRAMES_MARKER}: the test draws (presents a frame, or leaves a picture other than '
        'the blank screen); the driver comparison runs only these tests, and the plugin fails a '
        'test whose marker disagrees with what it did',
    )
    if judges_this_run(config=config):
        check = DrawsFramesCheck(
            config=config, report_only=bool(config.getoption(REPORT_ONLY_OPTION))
        )
        check.install()
        config.pluginmanager.register(check, name=CHECK_PLUGIN_NAME)
    directory: Path | None = config.getoption(FINGERPRINTS_OPTION)
    seed: int | None = config.getoption(SEED_OPTION)
    if environment_applies():
        if directory is None and os.environ.get(FINGERPRINTS_VARIABLE):
            directory = Path(os.environ[FINGERPRINTS_VARIABLE])
        if seed is None and os.environ.get(SEED_VARIABLE):
            seed = int(os.environ[SEED_VARIABLE])
    request_path: Path | None = config.getoption(IMAGES_REQUEST_OPTION)
    if directory is None:
        if request_path is not None:
            message = f'{IMAGES_REQUEST_OPTION} needs {FINGERPRINTS_OPTION}'
            raise pytest.UsageError(message)
        return
    image_request = None
    if request_path is not None:
        try:
            image_request = FrameImageRequest.model_validate_json(
                request_path.read_text(encoding='utf-8')
            )
        except (OSError, ValueError) as error:
            message = f'{IMAGES_REQUEST_OPTION} {request_path}: {error}'
            raise pytest.UsageError(message) from None
    # Absolute: a test may change the working directory
    recorder = FrameFingerprintRecorder(
        directory=config.invocation_params.dir / directory,
        image_request=image_request,
        seed=seed,
    )
    recorder.install()
    config.pluginmanager.register(recorder, name=RECORDER_PLUGIN_NAME)


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Deselect every test not marked draws_frames, given ``--draws-frames-only``.

    It runs last, after the caller's ``-m`` and ``-k`` have selected.

    A run that collected tests none of which is marked stops: its comparison would compare
    nothing and agree (a lost or misapplied marker would make the driver comparison a no-op).

    Args:
        config: pytest's configuration.
        items: The collected tests (kept in place: the drawing ones).

    Raises:
        pytest.UsageError: If tests were collected and none is marked draws_frames.

    """
    if not config.getoption(DRAWS_FRAMES_ONLY_OPTION):
        return
    drawing = [item for item in items if item.get_closest_marker(DRAWS_FRAMES_MARKER)]
    if items and not drawing:
        message = (
            f'{DRAWS_FRAMES_ONLY_OPTION}: none of the {len(items)} collected test(s) is marked '
            f'{DRAWS_FRAMES_MARKER}, so there is nothing to compare'
        )
        raise pytest.UsageError(message)
    others = [item for item in items if not item.get_closest_marker(DRAWS_FRAMES_MARKER)]
    if others:
        config.hook.pytest_deselected(items=others)
    items[:] = drawing


def pytest_unconfigure(config: pytest.Config) -> None:
    """Put back the display's present functions, last wrapper first.

    The recorder wraps the check's wrappers (it is installed after them), so it is undone
    first: each then puts back exactly what it found.

    Args:
        config: pytest's configuration.

    """
    recorder = config.pluginmanager.get_plugin(RECORDER_PLUGIN_NAME)
    if isinstance(recorder, FrameFingerprintRecorder):
        recorder.uninstall()
        config.pluginmanager.unregister(recorder)
    check = config.pluginmanager.get_plugin(CHECK_PLUGIN_NAME)
    if isinstance(check, DrawsFramesCheck):
        check.uninstall()
        config.pluginmanager.unregister(check)
