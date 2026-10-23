"""scripts/driver_frame_matrix.py compares every driver configuration's frames with every other's.

The runs are fabricated as in tests/test_compare_driver_frames.py: fingerprint files written as
the frame fingerprints plugin writes them, and PNG frames saved where its image request saves
them. Four configurations, dummy run twice:

- NODE_A: cocoa draws another present 1 (one pixel differs in the re-run's images);
- NODE_B: both x11 configurations draw another final frame (the re-run does not reproduce it);
- NODE_C: every configuration agrees;
- NODE_D: differs between the two dummy runs (nondeterministic: in no pair);
- NODE_E: marked frames_vary (in no pair);
- NODE_F: x11-linux did not record it;
- NODE_G: three groups (dummy | cocoa and x11-macos | x11-linux); no images saved, and the
  x11-linux re-run lacks it.
"""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING

import noxfile
import pytest
from scripts.compare_driver_frames import LabelledRun
from scripts.driver_frame_matrix import (
    MATRIX_JSON_NAME,
    MATRIX_MARKDOWN_NAME,
    DriverMatrix,
    build_matrix,
    compare_pair_images,
    describe_groups,
    main,
    markdown_cell,
    matrix_markdown,
    name_list,
    run,
    summary_text,
)

from glitchygames.exit_codes import ExitCode
from glitchygames.testing.frame_fingerprints import RecordedFrames, images_folder_name
from tests.test_compare_driver_frames import RED, frame, record, save_colour_frame, write_run

if TYPE_CHECKING:
    from pathlib import Path

NODE_A = 'tests/test_a.py::test_cocoa_differs'
NODE_B = 'tests/test_a.py::test_x11_differs[a|b]'
NODE_C = 'tests/test_c.py::test_agrees'
NODE_D = 'tests/test_d.py::test_nondeterministic'
NODE_E = 'tests/test_e.py::test_frames_vary'
NODE_F = 'tests/test_f.py::test_missing_on_x11_linux'
NODE_G = 'tests/test_g.py::test_three_groups'
CONFIGURATIONS = ('dummy', 'cocoa', 'x11-macos', 'x11-linux')


def records_for(*, label: str, repeat: int = 0) -> list[RecordedFrames]:
    """Return a configuration's fabricated records (see the module docstring).

    Args:
        label: The configuration.
        repeat: Which run of it (dummy's second run differs on NODE_D).

    Returns:
        The records.

    """
    is_x11 = label.startswith('x11')
    records = [
        record(
            nodeid=NODE_A,
            presented=(frame('a'), frame('cocoa' if label == 'cocoa' else 'b')),
            final=frame('c'),
        ),
        record(nodeid=NODE_B, presented=(frame('a'),), final=frame('x11' if is_x11 else 'b')),
        record(nodeid=NODE_C, presented=(frame('a'),), final=frame('c')),
        record(nodeid=NODE_D, final=frame(f'run {repeat}')),
        RecordedFrames(
            nodeid=NODE_E,
            outcome='passed',
            presented=(frame(label),),
            final=None,
            frames_vary_reason='measured frame times',
        ),
        record(
            nodeid=NODE_G,
            final=frame({'dummy': 'g1', 'cocoa': 'g2', 'x11-macos': 'g2'}.get(label, 'g3')),
            outcome='failed' if label == 'x11-linux' else 'passed',
        ),
    ]
    if label != 'x11-linux':
        records.append(record(nodeid=NODE_F, final=frame('f')))
    return records


@pytest.fixture
def runs(tmp_path) -> list[LabelledRun]:
    """Write the five fabricated runs.

    Returns:
        dummy's two runs, then cocoa's, x11-macos's and x11-linux's.

    """
    labelled = [
        LabelledRun(
            label='dummy',
            directory=write_run(
                directory=tmp_path / f'dummy-{repeat + 1}',
                records=records_for(label='dummy', repeat=repeat),
            ),
        )
        for repeat in range(2)
    ]
    labelled.extend(
        LabelledRun(
            label=label,
            directory=write_run(directory=tmp_path / label, records=records_for(label=label)),
        )
        for label in CONFIGURATIONS[1:]
    )
    return labelled


@pytest.fixture
def reruns(tmp_path) -> list[LabelledRun]:
    """Write each configuration's re-run of the differing tests, with NODE_A's frames.

    NODE_A's present 1 is red everywhere, with one white pixel on cocoa; its final frame is red
    everywhere. NODE_B agrees everywhere in the re-run. NODE_G is as first recorded, without
    images, and missing from x11-linux's re-run.

    Returns:
        The re-runs, in configuration order.

    """
    labelled: list[LabelledRun] = []
    for label in CONFIGURATIONS:
        directory = tmp_path / f'{label}-images'
        records = [each for each in records_for(label=label) if each.nodeid in {NODE_A, NODE_G}]
        records.append(record(nodeid=NODE_B, presented=(frame('a'),), final=frame('b')))
        if label == 'x11-linux':
            records = [each for each in records if each.nodeid != NODE_G]
        write_run(directory=directory, records=records)
        for position in (1, 2):
            save_colour_frame(
                directory=directory,
                nodeid=NODE_A,
                position=position,
                color=RED,
                changed_pixel=(0, 0) if label == 'cocoa' and position == 1 else None,
            )
        labelled.append(LabelledRun(label=label, directory=directory))
    return labelled


class TestNameList:
    """Names joined for a sentence."""

    @pytest.mark.parametrize(
        ('names', 'joined'),
        [((), ''), (('a',), 'a'), (('a', 'b'), 'a and b'), (('a', 'b', 'c'), 'a, b and c')],
    )
    def test_names_are_joined(self, names, joined):
        assert name_list(names) == joined


class TestDescribeGroups:
    """Each pattern of agreement in words."""

    @pytest.mark.parametrize(
        ('groups', 'not_recorded', 'pattern'),
        [
            ((('dummy', 'cocoa'),), (), 'all agree'),
            ((('dummy',), ('cocoa',)), (), 'cocoa differs from dummy'),
            ((('dummy', 'x11'), ('cocoa',)), (), 'cocoa differs from all others'),
            ((('dummy',), ('cocoa', 'x11')), (), 'dummy differs from all others'),
            (
                (('dummy', 'cocoa'), ('x11-macos', 'x11-linux')),
                (),
                'x11-macos and x11-linux differ from dummy and cocoa',
            ),
            ((('dummy',), ('cocoa',), ('x11',)), (), 'all differ'),
            (
                (('dummy',), ('cocoa', 'x11-macos'), ('x11-linux',)),
                (),
                'split: dummy | cocoa and x11-macos | x11-linux',
            ),
            ((('dummy', 'cocoa'),), ('x11',), 'all agree; not recorded on x11'),
        ],
    )
    def test_the_pattern(self, groups, not_recorded, pattern):
        assert describe_groups(groups=groups, not_recorded=not_recorded, baseline='dummy') == (
            pattern
        )


class TestBuildMatrix:
    """Every pair compared, nondeterministic and frames_vary tests left out."""

    def test_the_configurations_and_runs(self, runs):
        matrix = build_matrix(runs=runs, run_seconds={'dummy-1': 12.5})

        assert matrix.configurations == CONFIGURATIONS
        assert [(each.label, each.directory.name) for each in matrix.runs] == [
            ('dummy', 'dummy-1'),
            ('dummy', 'dummy-2'),
            ('cocoa', 'cocoa'),
            ('x11-macos', 'x11-macos'),
            ('x11-linux', 'x11-linux'),
        ]
        assert matrix.runs[0].seconds == 12.5
        assert matrix.runs[1].seconds is None
        assert matrix.runs[0].tests_recorded == 7
        assert matrix.runs[4].tests_recorded == 6
        assert matrix.runs[4].tests_failed == 1

    def test_every_pair_once_in_order(self, runs):
        matrix = build_matrix(runs=runs)

        assert [pair.name for pair in matrix.pairs] == [
            'dummy/cocoa',
            'dummy/x11-macos',
            'dummy/x11-linux',
            'cocoa/x11-macos',
            'cocoa/x11-linux',
            'x11-macos/x11-linux',
        ]

    def test_each_pairs_differences(self, runs):
        matrix = build_matrix(runs=runs)

        differing = {
            pair.name: [difference.nodeid for difference in pair.differences]
            for pair in matrix.pairs
        }
        assert differing == {
            'dummy/cocoa': [NODE_A, NODE_G],
            'dummy/x11-macos': [NODE_B, NODE_G],
            'dummy/x11-linux': [NODE_B, NODE_G],
            'cocoa/x11-macos': [NODE_A, NODE_B],
            'cocoa/x11-linux': [NODE_A, NODE_B, NODE_G],
            'x11-macos/x11-linux': [NODE_G],
        }
        dummy_cocoa = matrix.pairs[0]
        assert dummy_cocoa.tests_compared == 5
        assert dummy_cocoa.difference_for(nodeid=NODE_C) is None
        dummy_linux = matrix.pairs[2]
        assert dummy_linux.only_in_first == (NODE_F,)
        assert dummy_linux.only_in_second == ()
        assert dummy_linux.tests_compared == 4

    def test_the_tests_and_their_patterns(self, runs):
        matrix = build_matrix(runs=runs)

        assert {test.nodeid: test.pattern for test in matrix.tests} == {
            NODE_A: 'cocoa differs from all others',
            NODE_B: 'x11-macos and x11-linux differ from dummy and cocoa',
            NODE_F: 'all agree; not recorded on x11-linux',
            NODE_G: 'split: dummy | cocoa and x11-macos | x11-linux',
        }
        test_f = next(test for test in matrix.tests if test.nodeid == NODE_F)
        assert test_f.groups == (('dummy', 'cocoa', 'x11-macos'),)
        assert test_f.not_recorded == ('x11-linux',)
        assert test_f.file == 'tests/test_f.py'

    def test_nondeterministic_and_frames_vary_tests_are_apart(self, runs):
        matrix = build_matrix(runs=runs)

        assert [repeat.nodeids for repeat in matrix.repeats] == [frozenset({NODE_D})]
        assert matrix.frames_vary == {NODE_E: 'measured frame times'}


class TestPairImages:
    """Every differing pair's re-run frames compared as images."""

    def test_a_reproduced_difference_has_its_images(self, runs, reruns, tmp_path):
        output = tmp_path / 'report'
        matrix = compare_pair_images(matrix=build_matrix(runs=runs), reruns=reruns, output=output)

        dummy_cocoa = matrix.pairs[0]
        images = matrix.images_for(pair=dummy_cocoa, nodeid=NODE_A)
        assert images is not None
        assert images.reproduced
        assert [each.differing_pixels for each in images.comparisons] == [1]
        folder = output / 'differences' / 'dummy-vs-cocoa' / images_folder_name(nodeid=NODE_A)
        assert images.comparisons[0].difference_image == folder / 'difference-frame-1.png'
        assert {path.name for path in folder.iterdir()} == {
            'dummy-frame-1.png',
            'cocoa-frame-1.png',
            'difference-frame-1.png',
        }

    def test_a_difference_that_does_not_reproduce(self, runs, reruns, tmp_path):
        matrix = compare_pair_images(
            matrix=build_matrix(runs=runs), reruns=reruns, output=tmp_path / 'report'
        )

        images = matrix.images_for(pair=matrix.pairs[1], nodeid=NODE_B)
        assert images is not None
        assert not images.reproduced
        assert images.comparisons == ()

    def test_a_test_missing_from_a_rerun(self, runs, reruns, tmp_path):
        matrix = compare_pair_images(
            matrix=build_matrix(runs=runs), reruns=reruns, output=tmp_path / 'report'
        )

        x11_pair = matrix.pairs[5]
        images = matrix.images_for(pair=x11_pair, nodeid=NODE_G)
        assert images is not None
        assert not images.reproduced

    def test_no_images_for_an_agreeing_pair(self, runs, reruns, tmp_path):
        matrix = compare_pair_images(
            matrix=build_matrix(runs=runs), reruns=reruns, output=tmp_path / 'report'
        )

        assert matrix.images_for(pair=matrix.pairs[0], nodeid=NODE_B) is None


class TestMarkdown:
    """matrix.md: runs, pairs, patterns, a table per file and per test."""

    @pytest.fixture
    def markdown(self, runs, reruns, tmp_path) -> str:
        """The report with images.

        Returns:
            The Markdown.

        """
        output = tmp_path / 'report'
        matrix = compare_pair_images(
            matrix=build_matrix(runs=runs, run_seconds={'cocoa': 61.4}),
            reruns=reruns,
            output=output,
        )
        return matrix_markdown(matrix=matrix, output=output)

    def test_the_runs_table(self, markdown):
        assert '| cocoa | cocoa | 7 | 0 | 61 |' in markdown
        assert '| x11-linux | x11-linux | 6 | 1 |  |' in markdown

    def test_the_pair_summary(self, markdown):
        assert '| dummy/cocoa | 5 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |' in markdown
        assert '| dummy/x11-linux | 4 | 2 | 2 | 0 | 0 | 0 | 0 | 1 | 0 |' in markdown

    def test_the_patterns(self, markdown):
        assert '| cocoa differs from all others | 1 |' in markdown

    def test_the_file_table(self, markdown):
        assert '| tests/test_a.py | 2 | 1 | 1 | 1 | 2 | 2 | 0 |' in markdown

    def test_the_test_cells(self, markdown):
        folder = images_folder_name(nodeid=NODE_A)
        assert (
            '| test_cocoa_differs | cocoa differs from all others | **frame 1** (pixels): '
            f'[1 px](differences/dummy-vs-cocoa/{folder}/difference-frame-1.png) | agree |'
        ) in markdown
        assert (
            '| test_x11_differs[a\\|b] | x11-macos and x11-linux differ from dummy and cocoa | '
            'agree | **frame 1 final** (pixels): not reproduced |'
        ) in markdown
        assert (
            '| test_missing_on_x11_linux | all agree; not recorded on x11-linux | agree | agree '
            '| n/a |'
        ) in markdown
        assert (
            '| test_three_groups | split: dummy | cocoa and x11-macos | x11-linux | '
            '**frame 0 final** (pixels): no image saved on both drivers'
        ) in markdown
        assert '<details><summary>tests/test_a.py (2 tests)</summary>' in markdown

    def test_the_tests_left_out(self, markdown):
        assert '## Nondeterministic on dummy (2 runs; not compared)' in markdown
        assert f'- {NODE_D}: the final frame differs (pixels)' in markdown
        assert f'- {NODE_E}: measured frame times' in markdown

    def test_without_images_a_cell_has_the_frame_only(self, runs, tmp_path):
        markdown = matrix_markdown(matrix=build_matrix(runs=runs), output=tmp_path)

        assert '**frame 1** (pixels) | agree |' in markdown

    def test_a_frame_index_per_side_when_they_differ(self, tmp_path):
        first = write_run(
            directory=tmp_path / 'a', records=[record(presented=(frame('a'),), final=frame('f'))]
        )
        second = write_run(directory=tmp_path / 'b', records=[record(final=frame('f'))])
        matrix = build_matrix(
            runs=[
                LabelledRun(label='dummy', directory=first),
                LabelledRun(label='cocoa', directory=second),
            ]
        )

        assert '**frame 0/0 final** (present count)' in matrix_markdown(
            matrix=matrix, output=tmp_path
        )

    def test_a_cell_escapes_a_bar(self):
        assert markdown_cell('a|b') == 'a\\|b'


class TestSummary:
    """The session's closing summary."""

    def test_the_pairs_patterns_and_nondeterministic_tests(self, runs):
        summary = summary_text(matrix=build_matrix(runs=runs))

        assert summary.startswith(
            'Driver matrix: dummy, cocoa, x11-macos, x11-linux (baseline dummy)\n'
        )
        assert '| dummy/cocoa | 5 | 2 |' in summary
        assert '| x11-macos and x11-linux differ from dummy and cocoa | 1 |' in summary
        assert f'Nondeterministic (not compared): 1\n  {NODE_D}\n' in summary

    def test_when_everything_agrees(self, tmp_path):
        records = [record(final=frame('f'))]
        matrix = build_matrix(
            runs=[
                LabelledRun(
                    label='dummy', directory=write_run(directory=tmp_path / 'a', records=records)
                ),
                LabelledRun(
                    label='cocoa', directory=write_run(directory=tmp_path / 'b', records=records)
                ),
            ]
        )

        assert matrix.tests == ()
        assert 'Every configuration agrees on every compared test.' in summary_text(matrix=matrix)
        assert '## Tests' not in matrix_markdown(matrix=matrix, output=tmp_path)


class TestCommandLine:
    """The command writes matrix.md, matrix.json and the image request; prints the summary."""

    def run_arguments(self, runs: list[LabelledRun]) -> list[str]:
        """Return the runs as LABEL=DIRECTORY arguments."""
        return [f'{each.label}={each.directory}' for each in runs]

    def test_the_first_pass_writes_the_report_and_the_request(self, runs, tmp_path, capsys):
        output = tmp_path / 'report'
        request = output / 'image-request.json'
        seconds = tmp_path / 'run-seconds.json'
        seconds.write_text(json.dumps({'dummy-1': 3.0}), encoding='utf-8')

        exit_code = run(
            arguments=[
                *self.run_arguments(runs),
                f'--output={output}',
                f'--image-request={request}',
                f'--run-seconds={seconds}',
            ]
        )

        assert exit_code == ExitCode.SUCCESS
        assert set(json.loads(request.read_text(encoding='utf-8'))['positions_by_test']) == {
            NODE_A,
            NODE_B,
            NODE_G,
        }
        matrix = DriverMatrix.model_validate_json(
            (output / MATRIX_JSON_NAME).read_text(encoding='utf-8')
        )
        assert matrix.runs[0].seconds == 3.0
        assert '# Driver comparison matrix' in (output / MATRIX_MARKDOWN_NAME).read_text(
            encoding='utf-8'
        )
        printed = capsys.readouterr().out
        assert printed.endswith(f'Report: {output / MATRIX_MARKDOWN_NAME}\n')

    def test_the_second_pass_compares_the_reruns(self, runs, reruns, tmp_path):
        output = tmp_path / 'report'

        exit_code = run(
            arguments=[
                *self.run_arguments(runs),
                f'--output={output}',
                *(f'--rerun={each.label}={each.directory}' for each in reruns),
            ]
        )

        assert exit_code == ExitCode.SUCCESS
        assert '[1 px]' in (output / MATRIX_MARKDOWN_NAME).read_text(encoding='utf-8')

    def test_a_missing_run_directory(self, tmp_path, capsys):
        exit_code = run(arguments=[f'dummy={tmp_path / "none"}', f'--output={tmp_path}'])

        assert exit_code == ExitCode.MISSING_INPUT
        assert 'no such fingerprints directory' in capsys.readouterr().err

    def test_unreadable_run_seconds(self, runs, tmp_path, capsys):
        seconds = tmp_path / 'run-seconds.json'
        seconds.write_text('{not json', encoding='utf-8')

        exit_code = run(
            arguments=[
                *self.run_arguments(runs),
                f'--output={tmp_path}',
                f'--run-seconds={seconds}',
            ]
        )

        assert exit_code == ExitCode.UNUSABLE_INPUT
        assert 'unusable record or run times' in capsys.readouterr().err

    def test_an_unreadable_record(self, tmp_path):
        directory = tmp_path / 'run'
        directory.mkdir()
        (directory / 'gw0-1.jsonl').write_text('{"nodeid": 1}\n', encoding='utf-8')

        assert run(arguments=[f'dummy={directory}', f'--output={tmp_path}']) == (
            ExitCode.UNUSABLE_INPUT
        )

    def test_an_output_that_cannot_be_written(self, runs, tmp_path, capsys):
        output = tmp_path / 'a-file'
        output.write_text('', encoding='utf-8')

        exit_code = run(arguments=[*self.run_arguments(runs), f'--output={output}'])

        assert exit_code == ExitCode.CANNOT_WRITE_OUTPUT
        assert 'cannot write the output' in capsys.readouterr().err

    @pytest.mark.parametrize('empty_run_count', [1, 2])
    def test_runs_that_recorded_no_test_write_nothing_and_are_named(
        self, runs, tmp_path, capsys, empty_run_count
    ):
        """A run pytest ran no test in (``-- --help``) must not report full agreement (#192)."""
        empty_runs = [
            LabelledRun(
                label=label, directory=write_run(directory=tmp_path / f'{label}-empty', records=[])
            )
            for label in CONFIGURATIONS[1 : 1 + empty_run_count]
        ]
        output = tmp_path / 'report'
        request = output / 'image-request.json'

        exit_code = run(
            arguments=[
                *self.run_arguments([*runs[:2], *empty_runs]),
                f'--output={output}',
                f'--image-request={request}',
            ]
        )

        assert exit_code == ExitCode.UNUSABLE_INPUT
        assert not output.exists()
        captured = capsys.readouterr()
        assert not captured.out
        named_runs = ', '.join(
            f'{empty_run.directory.name} ({empty_run.label}, {empty_run.directory})'
            for empty_run in empty_runs
        )
        noun = 'run' if empty_run_count == 1 else 'runs'
        assert captured.err == (
            f'No report written: {noun} {named_runs} recorded no test (did pytest run the '
            f'suite? --help or --collect-only run no test), so nothing could be compared\n'
        )

    def test_an_earlier_report_is_kept_when_a_run_recorded_no_test(self, runs, tmp_path):
        output = tmp_path / 'report'
        assert run(arguments=[*self.run_arguments(runs), f'--output={output}']) == (
            ExitCode.SUCCESS
        )
        earlier_report = (output / MATRIX_MARKDOWN_NAME).read_text(encoding='utf-8')
        empty_run = LabelledRun(
            label='cocoa', directory=write_run(directory=tmp_path / 'cocoa-empty', records=[])
        )

        exit_code = run(arguments=[*self.run_arguments([runs[0], empty_run]), f'--output={output}'])

        assert exit_code == ExitCode.UNUSABLE_INPUT
        assert (output / MATRIX_MARKDOWN_NAME).read_text(encoding='utf-8') == earlier_report

    def test_main_exits_with_the_code(self, runs, tmp_path, monkeypatch):
        monkeypatch.setattr(
            sys, 'argv', ['driver_frame_matrix', *self.run_arguments(runs), f'--output={tmp_path}']
        )

        with pytest.raises(SystemExit) as raised:
            main()

        assert raised.value.code == ExitCode.SUCCESS


class LoggingSession:
    """Stands in for the nox session the folder helpers log through: keeps each message."""

    def __init__(self) -> None:
        """Start with no messages."""
        self.messages: list[str] = []

    def log(self, message: str) -> None:
        """Keep a message."""
        self.messages.append(message)


def write_comparison(*, folder: Path, report: str) -> None:
    """Write a comparison folder holding a report and one run."""
    (folder / 'dummy-1').mkdir(parents=True)
    (folder / MATRIX_MARKDOWN_NAME).write_text(report, encoding='utf-8')


class TestComparisonFolders:
    """compare-drivers never replaces the last complete comparison with a failed one (#192)."""

    @pytest.fixture
    def folders(self, tmp_path) -> tuple[Path, Path, Path]:
        """Return the output, previous and failed folders (none made).

        Returns:
            The three folders.

        """
        return tmp_path / 'nox', tmp_path / 'nox-previous', tmp_path / 'nox-failed'

    def test_a_failed_comparison_puts_the_last_complete_one_back(self, folders):
        output, previous, failed = folders
        write_comparison(folder=output, report='complete')
        session = LoggingSession()

        noxfile._set_aside_previous_comparison(output=output, previous=previous)
        assert list(output.iterdir()) == []
        (output / 'dummy-1').mkdir()
        noxfile._restore_previous_comparison(
            session, output=output, previous=previous, failed=failed
        )

        assert (output / MATRIX_MARKDOWN_NAME).read_text(encoding='utf-8') == 'complete'
        assert not previous.exists()
        assert [path.name for path in failed.iterdir()] == ['dummy-1']
        assert session.messages == [
            (
                f'The comparison did not finish: its runs are in {failed}; the last complete '
                f'comparison is still in {output}'
            )
        ]

    def test_a_failure_with_no_earlier_comparison_leaves_no_report(self, folders):
        output, previous, failed = folders
        session = LoggingSession()

        noxfile._set_aside_previous_comparison(output=output, previous=previous)
        noxfile._restore_previous_comparison(
            session, output=output, previous=previous, failed=failed
        )

        assert not output.exists()
        assert failed.is_dir()
        assert session.messages == [
            (
                f'The comparison did not finish: its runs are in {failed}; there is no earlier '
                f'complete comparison'
            )
        ]

    def test_a_killed_sessions_previous_folder_stays_the_last_complete_one(self, folders):
        output, previous, _failed = folders
        write_comparison(folder=previous, report='complete')
        write_comparison(folder=output, report='unfinished')

        noxfile._set_aside_previous_comparison(output=output, previous=previous)

        assert list(output.iterdir()) == []
        assert (previous / MATRIX_MARKDOWN_NAME).read_text(encoding='utf-8') == 'complete'
