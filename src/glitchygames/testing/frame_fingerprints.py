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

It records only when asked (otherwise it registers the ``frames_vary`` marker and does
nothing)::

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
files, at ``frame_image_path(directory=DIRECTORY, nodeid=..., position=...)``.

``--frame-fingerprints-seed SEED`` makes the master seed an engine draws when it is given no
``--random-seed`` depend on SEED and the test's node id alone (``SeededDraws``), so tests that
start engines unseeded draw the same pictures in every run and can be compared; without it they
are nondeterministic by design.

The fingerprint costs about 0.75 ms per present at 800x600 (0.3 ms for the RGB bytes, 0.4 ms for
the hash), plus about 0.3 ms on a display with per-pixel alpha.
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
from pydantic import BaseModel, ConfigDict

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
    """The frames to save as PNG files: positions (in ``RecordedFrames.frames``) by node id."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    positions_by_test: dict[str, tuple[int, ...]]


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
            if nodeid is None:
                present(*args, **kwargs)
                return
            shown = fingerprint_display()
            present(*args, **kwargs)
            self.record_frame(nodeid=nodeid, shown=shown, position=len(self.presented))
            self.presented.append(None if shown is None else shown[0])

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
            self.final = fingerprint_display()
            self.final_driver = display_driver()
            self.record_frame(nodeid=item.nodeid, shown=self.final, position=len(self.presented))

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
            )
            with self.records_path.open('a', encoding='utf-8') as records_file:
                records_file.write(record.model_dump_json() + '\n')
            self.current_nodeid = None
            self.presented = []
        return report


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


def environment_applies() -> bool:
    """Tell whether the recording variables are meant for this process.

    Returns:
        True when GLITCHYGAMES_FRAME_FINGERPRINTS_OWNER names this process or its parent (an
        xdist worker's controller).

    """
    owner = os.environ.get(OWNER_VARIABLE, '')
    return owner in {str(os.getpid()), str(os.getppid())}


def pytest_configure(config: pytest.Config) -> None:
    """Register the frames_vary marker; install the recorder when asked to record.

    Recording is asked for by ``--frame-fingerprints`` (or GLITCHYGAMES_FRAME_FINGERPRINTS);
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


def pytest_unconfigure(config: pytest.Config) -> None:
    """Put back the display's present functions.

    Args:
        config: pytest's configuration.

    """
    recorder = config.pluginmanager.get_plugin(RECORDER_PLUGIN_NAME)
    if isinstance(recorder, FrameFingerprintRecorder):
        recorder.uninstall()
        config.pluginmanager.unregister(recorder)
