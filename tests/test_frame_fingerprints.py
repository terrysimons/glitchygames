"""The frame fingerprints plugin (glitchygames/testing/frame_fingerprints.py).

The plugin records a fingerprint of every frame each test presents, for comparing SDL drivers
(scripts/compare_driver_frames.py, ``nox -s compare-drivers``). It is not loaded in normal runs,
so the pytester runs here load it with ``-p``, in process: the plugin's docstring disables
assertion rewriting for it (it makes no assertions), so pytest does not warn that this process
imported it already.
"""

from __future__ import annotations

import hashlib
import json
import os
import textwrap
from typing import TYPE_CHECKING

import pygame
import pytest

from glitchygames import randomness
from glitchygames.randomness import SEED_BITS
from glitchygames.testing import frame_fingerprints
from glitchygames.testing.frame_fingerprints import (
    DIGEST_HEX_LENGTH,
    FINGERPRINTS_OPTION,
    FINGERPRINTS_VARIABLE,
    IMAGES_FOLDER_HASH_LENGTH,
    IMAGES_FOLDER_NAME_LENGTH,
    IMAGES_REQUEST_OPTION,
    OWNER_VARIABLE,
    SEED_OPTION,
    SEED_VARIABLE,
    SEEDED_DRAW_MAXIMUM_BITS,
    FrameFingerprint,
    FrameFingerprintRecorder,
    FrameImageRequest,
    RecordedFrames,
    SeededDraws,
    fingerprint_display,
    frame_image_path,
    frame_position_name,
    images_folder_name,
    read_recorded_frames,
    save_frame_image,
)
from tests.display_canvas import TEST_DISPLAY_SIZE, show_canvas, show_canvas_on_new_display

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

PLUGIN_MODULE = 'glitchygames.testing.frame_fingerprints'
RED = (200, 30, 40)
GREEN = (20, 180, 60)
BLUE = (30, 40, 210)

# Inner tests run by pytester: each draws, presents and leaves the display filled with a colour
# (the inner run has no canvas rule of its own; the outer test shows the canvas afterwards)
INNER_TESTS = textwrap.dedent(
    """
    import pygame
    import pytest


    @pytest.fixture
    def green_display():
        display = pygame.display.get_surface()
        display.fill((20, 180, 60))
        pygame.display.flip()
        return display


    def test_presents_twice_then_draws_blue(green_display):
        green_display.fill((200, 30, 40))
        pygame.display.flip()
        pygame.display.update(pygame.Rect(0, 0, 10, 10))
        green_display.fill((30, 40, 210))


    def test_never_presents():
        pygame.display.get_surface().fill((30, 40, 210))


    def test_fails_after_a_present():
        pygame.display.flip()
        raise AssertionError('fails on purpose')


    @pytest.mark.skip(reason='never runs: no record')
    def test_skipped():
        pass
    """
)
# An inner test that writes two unseeded master seed draws to the file the variable names
SEEDS_OUTPUT_VARIABLE = 'FRAME_FINGERPRINTS_TEST_SEEDS_OUTPUT'
INNER_SEEDS_TEST = textwrap.dedent(
    f"""
    import json
    import os

    from glitchygames.randomness import seed_engine_random


    def test_draws_two_seeds():
        seeds = [seed_engine_random(), seed_engine_random()]
        with open(os.environ[{SEEDS_OUTPUT_VARIABLE!r}], 'w') as seeds_file:
            json.dump(seeds, seeds_file)
    """
)
PRESENTS_TWICE = 'test_inner.py::test_presents_twice_then_draws_blue'
NEVER_PRESENTS = 'test_inner.py::test_never_presents'
FAILS = 'test_inner.py::test_fails_after_a_present'


def colour_fingerprint(*, color: tuple[int, int, int], size: tuple[int, int]) -> FrameFingerprint:
    """Return the fingerprint of an opaque frame filled with one colour.

    Returns:
        The fingerprint, computed independently of the plugin.

    """
    rgb_bytes = bytes(color) * (size[0] * size[1])
    return FrameFingerprint(
        width=size[0],
        height=size[1],
        digest=hashlib.sha256(rgb_bytes).hexdigest()[:DIGEST_HEX_LENGTH],
    )


@pytest.fixture(autouse=True)
def no_recording_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear the recording variables a comparing run sets (in-process runs here read them)."""
    for name in (FINGERPRINTS_VARIABLE, SEED_VARIABLE, OWNER_VARIABLE):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def inner_tests(pytester: pytest.Pytester) -> Iterator[pytest.Pytester]:
    """A pytester directory holding the inner tests, the display shown again afterwards.

    Yields:
        The pytester.

    """
    pytester.makepyfile(test_inner=INNER_TESTS)
    yield pytester
    show_canvas_on_new_display(size=TEST_DISPLAY_SIZE)


class TestRecordingARun:
    """A run with --frame-fingerprints writes each test's frames, in present order."""

    def test_each_test_gets_its_presents_and_final_frame(self, inner_tests, tmp_path):
        """Setup and body presents count, in order; the final frame is the display as left."""
        directory = tmp_path / 'run'
        result = inner_tests.runpytest_inprocess(
            '-p', PLUGIN_MODULE, f'{FINGERPRINTS_OPTION}={directory}'
        )
        result.assert_outcomes(passed=2, failed=1, skipped=1)

        records = read_recorded_frames(directory=directory)
        size = pygame.display.get_surface().get_size()
        green = colour_fingerprint(color=GREEN, size=size)
        red = colour_fingerprint(color=RED, size=size)
        blue = colour_fingerprint(color=BLUE, size=size)
        assert set(records) == {PRESENTS_TWICE, NEVER_PRESENTS, FAILS}
        driver = pygame.display.get_driver()
        assert records[PRESENTS_TWICE] == RecordedFrames(
            nodeid=PRESENTS_TWICE,
            outcome='passed',
            presented=(green, red, red),
            final=blue,
            run_driver=os.environ['SDL_VIDEODRIVER'],
            final_driver=driver,
        )
        assert records[PRESENTS_TWICE].final_on_run_driver
        assert records[PRESENTS_TWICE].frames == (green, red, red, blue)
        assert records[NEVER_PRESENTS].presented == ()
        assert records[NEVER_PRESENTS].final == blue
        assert records[FAILS].outcome == 'failed'
        assert len(records[FAILS].presented) == 1

    def test_the_display_functions_are_put_back_after_the_run(self, inner_tests, tmp_path):
        """The wrappers live only as long as the inner run."""
        flip_before = pygame.display.flip
        update_before = pygame.display.update

        inner_tests.runpytest_inprocess(
            '-p', PLUGIN_MODULE, f'{FINGERPRINTS_OPTION}={tmp_path / "run"}'
        )

        assert pygame.display.flip is flip_before
        assert pygame.display.update is update_before

    def test_without_the_option_nothing_is_recorded(self, inner_tests):
        """Loading the plugin alone changes nothing: no files are written."""
        result = inner_tests.runpytest_inprocess('-p', PLUGIN_MODULE)

        result.assert_outcomes(passed=2, failed=1, skipped=1)
        assert not list(inner_tests.path.glob('**/*.jsonl'))

    def test_requested_frames_are_saved_as_images(self, inner_tests, tmp_path):
        """--frame-images-request saves the named positions of the named tests as PNG files."""
        directory = tmp_path / 'run'
        request_path = tmp_path / 'request.json'
        request = FrameImageRequest(positions_by_test={PRESENTS_TWICE: (1, 3)})
        request_path.write_text(request.model_dump_json(), encoding='utf-8')

        inner_tests.runpytest_inprocess(
            '-p',
            PLUGIN_MODULE,
            f'{FINGERPRINTS_OPTION}={directory}',
            f'{IMAGES_REQUEST_OPTION}={request_path}',
        )

        saved = sorted(path.name for path in (directory / 'images').glob('*/*.png'))
        assert saved == ['frame-1.png', 'frame-3.png']
        red_image = pygame.image.load(
            frame_image_path(directory=directory, nodeid=PRESENTS_TWICE, position=1)
        )
        blue_image = pygame.image.load(
            frame_image_path(directory=directory, nodeid=PRESENTS_TWICE, position=3)
        )
        assert red_image.get_at((5, 5))[:3] == RED
        assert blue_image.get_at((5, 5))[:3] == BLUE

    def test_an_image_request_needs_the_fingerprints_option(self, inner_tests, tmp_path):
        """The request alone is a usage error."""
        request_path = tmp_path / 'request.json'
        request_path.write_text('{"positions_by_test": {}}', encoding='utf-8')

        result = inner_tests.runpytest_inprocess(
            '-p', PLUGIN_MODULE, f'{IMAGES_REQUEST_OPTION}={request_path}'
        )

        assert result.ret == pytest.ExitCode.USAGE_ERROR
        result.stderr.fnmatch_lines([f'*{IMAGES_REQUEST_OPTION} needs {FINGERPRINTS_OPTION}*'])

    @pytest.mark.parametrize(
        ('request_text', 'expected'),
        [(None, '*No such file*'), ('{"tests": []}', '*positions_by_test*')],
        ids=['missing file', 'not a request'],
    )
    def test_an_unreadable_image_request_is_a_usage_error(
        self, inner_tests, tmp_path, request_text, expected
    ):
        """A request file that is missing or not a FrameImageRequest stops the run."""
        request_path = tmp_path / 'request.json'
        if request_text is not None:
            request_path.write_text(request_text, encoding='utf-8')

        result = inner_tests.runpytest_inprocess(
            '-p',
            PLUGIN_MODULE,
            f'{FINGERPRINTS_OPTION}={tmp_path / "run"}',
            f'{IMAGES_REQUEST_OPTION}={request_path}',
        )

        assert result.ret == pytest.ExitCode.USAGE_ERROR
        result.stderr.fnmatch_lines([expected])

    def test_a_test_that_changes_directory_is_still_recorded(self, pytester, tmp_path):
        """The directory is resolved when the run starts, so a relative one survives chdir."""
        pytester.makepyfile(
            test_moves=textwrap.dedent(
                f"""
                import os

                def test_moves_away():
                    os.chdir({str(tmp_path)!r})
                """
            )
        )

        pytester.runpytest_inprocess('-p', PLUGIN_MODULE, f'{FINGERPRINTS_OPTION}=relative-run')

        assert list(read_recorded_frames(directory=pytester.path / 'relative-run')) == [
            'test_moves.py::test_moves_away'
        ]

    def test_a_display_quit_by_the_test_has_no_final_frame(self, pytester, tmp_path):
        """With the display gone the final frame is None (and nothing is saved for it)."""
        pytester.makepyfile(
            test_quits=textwrap.dedent(
                """
                import pygame

                def test_quits_the_display():
                    pygame.display.quit()
                """
            )
        )
        request_path = tmp_path / 'request.json'
        request = FrameImageRequest(
            positions_by_test={'test_quits.py::test_quits_the_display': (0,)}
        )
        request_path.write_text(request.model_dump_json(), encoding='utf-8')
        try:
            pytester.runpytest_inprocess(
                '-p',
                PLUGIN_MODULE,
                f'{FINGERPRINTS_OPTION}={tmp_path / "run"}',
                f'{IMAGES_REQUEST_OPTION}={request_path}',
            )
        finally:
            pygame.display.init()
            show_canvas_on_new_display(size=TEST_DISPLAY_SIZE)

        (record,) = read_recorded_frames(directory=tmp_path / 'run').values()
        assert record.final is None
        assert not (tmp_path / 'run' / 'images').exists()


class TestSeededMasterSeeds:
    """--frame-fingerprints-seed makes each test's unseeded master seed draws repeatable."""

    @staticmethod
    def drawn_seeds(
        *,
        pytester: pytest.Pytester,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        seed: int | None,
        run_name: str,
    ) -> list[int]:
        """Run an inner test that draws two master seeds; return them.

        The inner module is the same in every run (the draws depend on the test's node id);
        each run's output file is named by an environment variable.

        Returns:
            The seeds the inner test's two unseeded draws gave.

        """
        output = tmp_path / f'seeds-{run_name}.json'
        monkeypatch.setenv(SEEDS_OUTPUT_VARIABLE, str(output))
        pytester.makepyfile(test_seeds=INNER_SEEDS_TEST)
        arguments = ['-p', PLUGIN_MODULE, f'{FINGERPRINTS_OPTION}={tmp_path / "run"}']
        if seed is not None:
            arguments.append(f'{SEED_OPTION}={seed}')
        pytester.runpytest_inprocess(*arguments).assert_outcomes(passed=1)
        return json.loads(output.read_text(encoding='utf-8'))

    def test_a_seed_gives_the_same_draws_in_every_run(self, pytester, monkeypatch, tmp_path):
        """Two runs with the same seed draw the same master seeds; consecutive draws differ."""
        first_run = self.drawn_seeds(
            pytester=pytester, monkeypatch=monkeypatch, tmp_path=tmp_path, seed=7, run_name='a'
        )
        second_run = self.drawn_seeds(
            pytester=pytester, monkeypatch=monkeypatch, tmp_path=tmp_path, seed=7, run_name='b'
        )
        other_seed = self.drawn_seeds(
            pytester=pytester, monkeypatch=monkeypatch, tmp_path=tmp_path, seed=8, run_name='c'
        )

        assert first_run == second_run
        assert first_run[0] != first_run[1]
        assert other_seed != first_run
        assert all(0 <= seed < 2**SEED_BITS for seed in first_run)

    def test_without_a_seed_the_draws_stay_random(self, pytester, monkeypatch, tmp_path):
        """No seed: the draws come from secrets, different in every run."""
        first_run = self.drawn_seeds(
            pytester=pytester, monkeypatch=monkeypatch, tmp_path=tmp_path, seed=None, run_name='a'
        )
        second_run = self.drawn_seeds(
            pytester=pytester, monkeypatch=monkeypatch, tmp_path=tmp_path, seed=None, run_name='b'
        )

        assert first_run != second_run

    def test_the_real_secrets_module_is_put_back(self, pytester, monkeypatch, tmp_path):
        """After the run randomness draws from the secrets module again."""
        secrets_before = randomness.secrets

        self.drawn_seeds(
            pytester=pytester, monkeypatch=monkeypatch, tmp_path=tmp_path, seed=7, run_name='a'
        )

        assert randomness.secrets is secrets_before


class TestSeededDraws:
    """SeededDraws: secrets.randbits made repeatable."""

    def test_the_same_key_gives_the_same_sequence(self):
        """Two sequences of one key agree draw for draw; the draws themselves differ."""
        first = SeededDraws(key='7:test_a')
        second = SeededDraws(key='7:test_a')

        first_draws = [first.randbits(SEED_BITS) for _ in range(3)]

        assert first_draws == [second.randbits(SEED_BITS) for _ in range(3)]
        assert len(set(first_draws)) == len(first_draws)

    def test_keys_give_different_sequences(self):
        """Another key (another test) draws other numbers."""
        assert SeededDraws(key='7:test_a').randbits(SEED_BITS) != SeededDraws(
            key='7:test_b'
        ).randbits(SEED_BITS)

    @pytest.mark.parametrize('bits', [0, 1, 64, SEEDED_DRAW_MAXIMUM_BITS])
    def test_a_draw_has_at_most_the_asked_bits(self, bits):
        """A draw fits in the asked number of bits."""
        assert 0 <= SeededDraws(key='bits').randbits(bits) < 2**bits

    @pytest.mark.parametrize('bits', [-1, SEEDED_DRAW_MAXIMUM_BITS + 1])
    def test_more_bits_than_a_digest_are_refused(self, bits):
        """One SHA-256 digest is the most a draw holds."""
        with pytest.raises(ValueError, match='draws 0 to 256 bits'):
            SeededDraws(key='bits').randbits(bits)


class TestFingerprintDisplay:
    """fingerprint_display: the display as the window shows it."""

    def test_the_fingerprint_hashes_the_shown_rgb_bytes(self):
        """Size and digest come from the display's RGB bytes."""
        display = pygame.display.get_surface()
        display.fill(GREEN)

        fingerprint, rgb_bytes = fingerprint_display() or (None, b'')

        assert fingerprint == colour_fingerprint(color=GREEN, size=display.get_size())
        assert rgb_bytes == pygame.image.tobytes(display, 'RGB')
        show_canvas()

    def test_no_display_has_no_fingerprint(self):
        """Without a display module, or without pygame, there is nothing to fingerprint."""
        pygame.display.quit()
        try:
            assert fingerprint_display() is None
            pygame.quit()
            assert fingerprint_display() is None
        finally:
            pygame.init()
            show_canvas_on_new_display(size=TEST_DISPLAY_SIZE)

    def test_an_unreadable_display_has_no_fingerprint(self, mocker):
        """A display that cannot be read (an OpenGL one) has no fingerprint."""
        mocker.patch.object(
            frame_fingerprints,
            '_REAL_DISPLAY_GET_SURFACE',
            side_effect=pygame.error('cannot read an OpenGL display'),
        )

        assert fingerprint_display() is None


class TestTheRecorderBetweenTests:
    """The recorder object, used directly."""

    def test_presents_outside_a_test_are_passed_through_unrecorded(self, tmp_path):
        """With no test being recorded the wrappers only present."""
        recorder = FrameFingerprintRecorder(directory=tmp_path / 'run', image_request=None)
        recorder.install()
        try:
            pygame.display.flip()
            pygame.display.update()
        finally:
            recorder.uninstall()

        assert recorder.presented == []
        assert (tmp_path / 'run').is_dir()
        assert not list((tmp_path / 'run').iterdir())

    def test_a_failed_present_is_not_recorded(self, tmp_path):
        """A present that raises (no display) leaves no frame behind."""
        recorder = FrameFingerprintRecorder(directory=tmp_path / 'run', image_request=None)
        recorder.install()
        recorder.current_nodeid = 'test_x.py::test_x'
        pygame.display.quit()
        try:
            with pytest.raises(pygame.error):
                pygame.display.flip()
        finally:
            recorder.uninstall()
            pygame.display.init()
            show_canvas_on_new_display(size=TEST_DISPLAY_SIZE)

        assert recorder.presented == []


class TestNamesAndFiles:
    """Positions, image paths and reading the records."""

    def test_positions_are_named_presents_then_the_final_frame(self):
        """The last position is the final frame."""
        assert frame_position_name(position=0, frame_count=3) == 'present 0'
        assert frame_position_name(position=2, frame_count=3) == 'the final frame'

    def test_a_folder_name_is_readable_safe_and_unique(self):
        """Unsafe characters are replaced, long names cut, and a hash tells alike ids apart."""
        first = images_folder_name(nodeid='tests/a.py::test[x y]')
        second = images_folder_name(nodeid='tests/a.py::test[x/y]')
        long_name = images_folder_name(nodeid='t' * 500)

        assert first.startswith('tests_a.py_test_x_y_-')
        assert first != second
        assert len(long_name) == IMAGES_FOLDER_NAME_LENGTH + 1 + IMAGES_FOLDER_HASH_LENGTH

    def test_an_image_lives_in_its_tests_folder(self, tmp_path):
        """images/<test folder>/frame-<position>.png."""
        path = frame_image_path(directory=tmp_path, nodeid='tests/a.py::test_b', position=4)

        assert path == tmp_path / 'images' / images_folder_name(nodeid='tests/a.py::test_b') / (
            'frame-4.png'
        )

    def test_saved_images_hold_the_frame(self, tmp_path):
        """save_frame_image writes the RGB bytes at the fingerprint's size."""
        fingerprint = colour_fingerprint(color=RED, size=(3, 2))
        path = tmp_path / 'nested' / 'frame.png'

        save_frame_image(path=path, fingerprint=fingerprint, rgb_bytes=bytes(RED) * 6)

        image = pygame.image.load(path)
        assert image.get_size() == (3, 2)
        assert image.get_at((2, 1))[:3] == RED

    def test_records_are_read_from_every_file(self, tmp_path):
        """Each worker's file is read; blank lines are skipped; a repeated id keeps its last."""
        first = RecordedFrames(nodeid='t::a', outcome='passed', presented=(), final=None)
        repeated = first.model_copy(update={'outcome': 'failed'})
        other = RecordedFrames(nodeid='t::b', outcome='passed', presented=(None,), final=None)
        (tmp_path / 'gw0-1.jsonl').write_text(
            f'{first.model_dump_json()}\n\n{other.model_dump_json()}\n', encoding='utf-8'
        )
        (tmp_path / 'gw1-2.jsonl').write_text(f'{repeated.model_dump_json()}\n', encoding='utf-8')

        records = read_recorded_frames(directory=tmp_path)

        assert records == {'t::a': repeated, 't::b': other}

    def test_a_missing_directory_is_refused(self, tmp_path):
        """No directory: FileNotFoundError naming it."""
        with pytest.raises(FileNotFoundError, match='no such fingerprints directory'):
            read_recorded_frames(directory=tmp_path / 'absent')


class TestRunDriversAndMarkers:
    """Each record names its run's driver and its final display's, and any frames_vary reason."""

    @pytest.mark.parametrize(
        ('run_driver', 'final_driver', 'has_final', 'expected'),
        [
            ('cocoa', 'cocoa', True, True),
            ('cocoa', 'dummy', True, False),
            ('cocoa', None, False, False),
            (None, 'dummy', True, True),
        ],
        ids=['on the run driver', 'moved to dummy', 'no display', 'run driver unknown'],
    )
    def test_the_final_frame_counts_only_on_the_runs_driver(
        self, run_driver, final_driver, has_final, expected
    ):
        """A final display gone, or on another driver, is not the run's own picture."""
        record = RecordedFrames(
            nodeid='t::a',
            outcome='passed',
            presented=(),
            final=colour_fingerprint(color=RED, size=(2, 2)) if has_final else None,
            run_driver=run_driver,
            final_driver=final_driver,
        )

        assert record.final_on_run_driver is expected

    def test_a_frames_vary_reason_is_recorded(self, pytester, tmp_path):
        """The marker's reason goes into the record."""
        pytester.makepyfile(
            test_varies=textwrap.dedent(
                """
                import pytest

                @pytest.mark.frames_vary(reason='measured frame times')
                def test_varies():
                    pass
                """
            )
        )

        pytester.runpytest_inprocess(
            '-p', PLUGIN_MODULE, f'{FINGERPRINTS_OPTION}={tmp_path / "run"}'
        ).assert_outcomes(passed=1)

        (record,) = read_recorded_frames(directory=tmp_path / 'run').values()
        assert record.frames_vary_reason == 'measured frame times'


class TestEnvironmentActivation:
    """The recording variables apply in the process they name and its xdist workers only."""

    def test_variables_for_this_process_record_and_seed(self, pytester, monkeypatch, tmp_path):
        """Owner = this process: the run records into the directory, with the seed."""
        monkeypatch.setenv(FINGERPRINTS_VARIABLE, str(tmp_path / 'run'))
        monkeypatch.setenv(SEED_VARIABLE, '7')
        monkeypatch.setenv(OWNER_VARIABLE, str(os.getpid()))
        monkeypatch.setenv(SEEDS_OUTPUT_VARIABLE, str(tmp_path / 'seeds.json'))
        pytester.makepyfile(test_seeds=INNER_SEEDS_TEST)

        pytester.runpytest_inprocess('-p', PLUGIN_MODULE).assert_outcomes(passed=1)

        assert list(read_recorded_frames(directory=tmp_path / 'run')) == [
            'test_seeds.py::test_draws_two_seeds'
        ]
        expected_draws = SeededDraws(key='7:test_seeds.py::test_draws_two_seeds')
        seeds = json.loads((tmp_path / 'seeds.json').read_text(encoding='utf-8'))
        assert seeds == [expected_draws.randbits(SEED_BITS), expected_draws.randbits(SEED_BITS)]

    def test_variables_for_another_process_are_ignored(self, pytester, monkeypatch, tmp_path):
        """A pytest a test starts (another owner) records nothing."""
        monkeypatch.setenv(FINGERPRINTS_VARIABLE, str(tmp_path / 'run'))
        monkeypatch.setenv(OWNER_VARIABLE, '1')
        pytester.makepyfile(test_plain='def test_plain():\n    pass\n')

        pytester.runpytest_inprocess('-p', PLUGIN_MODULE).assert_outcomes(passed=1)

        assert not (tmp_path / 'run').exists()

    def test_options_win_over_the_variables(self, pytester, monkeypatch, tmp_path):
        """Given both, the run records where its options say, with their seed."""
        monkeypatch.setenv(FINGERPRINTS_VARIABLE, str(tmp_path / 'from-variable'))
        monkeypatch.setenv(SEED_VARIABLE, '7')
        monkeypatch.setenv(OWNER_VARIABLE, str(os.getpid()))
        monkeypatch.setenv(SEEDS_OUTPUT_VARIABLE, str(tmp_path / 'seeds.json'))
        pytester.makepyfile(test_seeds=INNER_SEEDS_TEST)

        pytester.runpytest_inprocess(
            '-p',
            PLUGIN_MODULE,
            f'{FINGERPRINTS_OPTION}={tmp_path / "from-option"}',
            f'{SEED_OPTION}=8',
        ).assert_outcomes(passed=1)

        assert not (tmp_path / 'from-variable').exists()
        assert list(read_recorded_frames(directory=tmp_path / 'from-option'))
        expected_draws = SeededDraws(key='8:test_seeds.py::test_draws_two_seeds')
        seeds = json.loads((tmp_path / 'seeds.json').read_text(encoding='utf-8'))
        assert seeds[0] == expected_draws.randbits(SEED_BITS)
