"""The draws_frames codemod (scripts/mark_drawing_tests.py).

Each test writes a small test file and a draws_frames report naming some of its tests, runs the
script from that directory, then collects the edited file with ``-m draws_frames``: the marked
tests must be exactly the listed ones.
"""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import pytest
from scripts.mark_drawing_tests import run

from glitchygames.exit_codes import ExitCode
from glitchygames.testing.frame_fingerprints import MARKERS_REPORT_PATH

if TYPE_CHECKING:
    from pathlib import Path

DRAWS = 'draws without the draws_frames marker (presented 1 frame(s)): add the marker'
IDLE = 'is marked draws_frames but draws nothing (no present): remove the marker'

TEST_FILE = textwrap.dedent(
    """
    import pytest


    def test_plain():
        pass


    def test_listed_function():
        pass


    class TestGroup:
        @pytest.mark.filterwarnings('ignore')
        def test_listed_method(self):
            pass

        def test_other_method(self):
            pass


    @pytest.mark.parametrize(
        'value',
        [
            1,
            pytest.param(2, id='two'),
            3,
        ],
    )
    def test_some_cases(value):
        pass


    @pytest.mark.parametrize('value', [1, 2])
    def test_every_case(value):
        pass
    """
)


def write_report(*, directory: Path, lines: dict[str, str]) -> None:
    """Write a draws_frames report.

    Args:
        directory: The directory the report's path is from.
        lines: The reasons by node id.

    """
    report = directory / MARKERS_REPORT_PATH
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(''.join(f'{nodeid}\t{reason}\n' for nodeid, reason in lines.items()))


def marked_node_ids(*, pytester: pytest.Pytester) -> set[str]:
    """Collect the directory's tests that carry the marker.

    Returns:
        Their node ids.

    """
    result = pytester.runpytest_inprocess(
        '--collect-only', '-q', '-n', '0', '-m', 'draws_frames', '-p', 'no:cacheprovider'
    )
    return {line for line in result.outlines if '::' in line}


@pytest.fixture
def test_directory(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> pytest.Pytester:
    """A directory holding the test file, made the working directory.

    Returns:
        The pytester.

    """
    pytester.makeini('[pytest]\nmarkers =\n    draws_frames: draws\n')
    pytester.makepyfile(test_listed=TEST_FILE)
    monkeypatch.chdir(pytester.path)
    return pytester


class TestMarking:
    """The listed tests, and only they, carry the marker afterwards."""

    def test_a_function_and_a_method_get_the_decorator(self, test_directory):
        """A plain function and a decorated method are marked above their decorators."""
        write_report(
            directory=test_directory.path,
            lines={
                'test_listed.py::test_listed_function': DRAWS,
                'test_listed.py::TestGroup::test_listed_method': DRAWS,
            },
        )

        assert run(arguments=[]) == ExitCode.SUCCESS

        assert marked_node_ids(pytester=test_directory) == {
            'test_listed.py::test_listed_function',
            'test_listed.py::TestGroup::test_listed_method',
        }
        text = (test_directory.path / 'test_listed.py').read_text()
        assert "    @pytest.mark.draws_frames\n    @pytest.mark.filterwarnings('ignore')\n" in text

    def test_only_the_listed_cases_of_a_parametrized_function_are_marked(self, test_directory):
        """Listed cases get pytest.param marks; an existing pytest.param gains marks=."""
        write_report(
            directory=test_directory.path,
            lines={
                'test_listed.py::test_some_cases[1]': DRAWS,
                'test_listed.py::test_some_cases[two]': DRAWS,
            },
        )

        assert run(arguments=[]) == ExitCode.SUCCESS

        assert marked_node_ids(pytester=test_directory) == {
            'test_listed.py::test_some_cases[1]',
            'test_listed.py::test_some_cases[two]',
        }
        text = (test_directory.path / 'test_listed.py').read_text()
        assert 'pytest.param(1, marks=pytest.mark.draws_frames)' in text
        assert "pytest.param(2, id='two', marks=pytest.mark.draws_frames)" in text

    def test_a_case_of_several_arguments_keeps_them_apart(self, pytester, monkeypatch):
        """A two-name case's tuple becomes pytest.param's two values, not one tuple value."""
        pytester.makeini('[pytest]\nmarkers =\n    draws_frames: draws\n')
        pytester.makepyfile(
            test_pairs=textwrap.dedent(
                """
                import pytest


                @pytest.mark.parametrize(('name', 'code'), [('ends', 0), ('fails', 1)])
                def test_pairs(name, code):
                    assert isinstance(name, str)
                    assert isinstance(code, int)
                """
            )
        )
        monkeypatch.chdir(pytester.path)
        write_report(directory=pytester.path, lines={'test_pairs.py::test_pairs[ends-0]': DRAWS})

        assert run(arguments=[]) == ExitCode.SUCCESS

        assert marked_node_ids(pytester=pytester) == {'test_pairs.py::test_pairs[ends-0]'}
        assert (
            "pytest.param('ends', 0, marks=pytest.mark.draws_frames)"
            in (pytester.path / 'test_pairs.py').read_text()
        )
        result = pytester.runpytest_inprocess('-q', '-n', '0', '-p', 'no:cacheprovider')
        result.assert_outcomes(passed=2)

    def test_a_function_whose_every_case_is_listed_is_marked_whole(self, test_directory):
        """All of a parametrized function's cases listed: the decorator goes on the function."""
        write_report(
            directory=test_directory.path,
            lines={
                'test_listed.py::test_every_case[1]': DRAWS,
                'test_listed.py::test_every_case[2]': DRAWS,
            },
        )

        assert run(arguments=[]) == ExitCode.SUCCESS

        text = (test_directory.path / 'test_listed.py').read_text()
        assert "@pytest.mark.draws_frames\n@pytest.mark.parametrize('value', [1, 2])" in text

    def test_an_already_marked_test_is_left_alone(self, test_directory):
        """Running it twice on the same report changes nothing the second time."""
        write_report(
            directory=test_directory.path, lines={'test_listed.py::test_listed_function': DRAWS}
        )
        run(arguments=[])
        once = (test_directory.path / 'test_listed.py').read_text()

        assert run(arguments=[]) == ExitCode.SUCCESS

        assert (test_directory.path / 'test_listed.py').read_text() == once

    def test_a_file_without_pytest_imported_gains_the_import(self, pytester, monkeypatch):
        """The marker needs pytest: the file gets ``import pytest``."""
        pytester.makeini('[pytest]\nmarkers =\n    draws_frames: draws\n')
        pytester.makepyfile(test_bare='import os\n\n\ndef test_bare():\n    assert os.sep\n')
        monkeypatch.chdir(pytester.path)
        write_report(directory=pytester.path, lines={'test_bare.py::test_bare': DRAWS})

        assert run(arguments=[]) == ExitCode.SUCCESS

        assert marked_node_ids(pytester=pytester) == {'test_bare.py::test_bare'}

    def test_a_file_keeps_its_line_endings(self, pytester, monkeypatch):
        """A CRLF file's added lines end in CRLF too."""
        pytester.makeini('[pytest]\nmarkers =\n    draws_frames: draws\n')
        path = pytester.path / 'test_crlf.py'
        path.write_bytes(b'import pytest\r\n\r\n\r\ndef test_crlf():\r\n    pass\r\n')
        monkeypatch.chdir(pytester.path)
        write_report(directory=pytester.path, lines={'test_crlf.py::test_crlf': DRAWS})

        assert run(arguments=[]) == ExitCode.SUCCESS

        assert b'@pytest.mark.draws_frames\r\ndef test_crlf' in path.read_bytes()
        assert b'\n' not in path.read_bytes().replace(b'\r\n', b'')


class TestRefusals:
    """A test it cannot place changes nothing and exits UNUSABLE_INPUT."""

    def test_a_node_id_pytest_does_not_collect_is_refused(self, test_directory, capsys):
        """A missing test is named, and no file changes (not even the placeable one)."""
        before = (test_directory.path / 'test_listed.py').read_text()
        write_report(
            directory=test_directory.path,
            lines={
                'test_listed.py::test_listed_function': DRAWS,
                'test_listed.py::test_gone': DRAWS,
            },
        )

        assert run(arguments=[]) == ExitCode.UNUSABLE_INPUT

        assert 'test_listed.py::test_gone: pytest does not collect it' in capsys.readouterr().err
        assert (test_directory.path / 'test_listed.py').read_text() == before

    def test_a_pytest_param_with_marks_already_is_refused(self, pytester, monkeypatch, capsys):
        """A listed case whose pytest.param has marks= cannot gain the marker there."""
        pytester.makeini('[pytest]\nmarkers =\n    draws_frames: draws\n    slow: slow\n')
        pytester.makepyfile(
            test_marked_param=textwrap.dedent(
                """
                import pytest


                @pytest.mark.parametrize(
                    'value', [pytest.param(1, marks=pytest.mark.slow), 2]
                )
                def test_cases(value):
                    pass
                """
            )
        )
        monkeypatch.chdir(pytester.path)
        write_report(directory=pytester.path, lines={'test_marked_param.py::test_cases[1]': DRAWS})

        assert run(arguments=[]) == ExitCode.UNUSABLE_INPUT

        assert 'already has marks=' in capsys.readouterr().err


class TestTheReport:
    """What it reads, and what it does with the other kind of disagreement."""

    def test_a_missing_report_exits_missing_input(self, tmp_path, monkeypatch):
        """No report, no work."""
        monkeypatch.chdir(tmp_path)

        assert run(arguments=[]) == ExitCode.MISSING_INPUT

    def test_marked_tests_that_draw_nothing_are_printed_to_remove_by_hand(
        self, test_directory, capsys
    ):
        """It never removes a marker; it names the test."""
        write_report(directory=test_directory.path, lines={'test_listed.py::test_plain': IDLE})

        assert run(arguments=[]) == ExitCode.SUCCESS

        assert 'remove the marker by hand: test_listed.py::test_plain' in capsys.readouterr().out
