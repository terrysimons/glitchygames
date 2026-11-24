"""Inner pytest runs (pytester): their tests' written order, and a configuration of their own.

The harness (tests/harness.py) does both for every test that uses ``pytester``.

Order:

pytest-randomly is blocked by the project's addopts, which an inner run does not read: it was
on in every inner run, shuffling their tests with a new seed each time, so what they left
behind (frames, state) changed from run to run (BUGS.md #255; #252's memory guard tests). The
harness blocks it for every test that uses ``pytester`` (``inner_runs_keep_their_order``).

Configuration: a pytester project held no configuration file, so pytest looked for one in the
folders above it. With the temporary folder inside the repository (a ``--basetemp`` there, or a
``TMPDIR`` in the checkout), the inner run took the repository's ``pyproject.toml``: its addopts
(xdist, 100% coverage) and its conftest. 25 tests in 7 files failed that way, their inner tests
passing
(bugs/2026-11-20-driver-comparison-end-to-end-tests-fail-inside-the-repository.md). The harness
gives every pytester project a lowest-precedence ``tox.ini`` (``give_project_its_own_config``),
so the search stops at the project, and a project's own configuration still wins.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from glitchygames.process import OutputCapture, run_command
from tests.harness import OWN_CONFIG_FILE_NAME, give_project_its_own_config

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

# How long a bare inner pytest run may take
INNER_RUN_TIMEOUT_SECONDS = 120
# An enclosing project's pytest settings (as the repository's pyproject.toml holds its own)
ENCLOSING_PROJECT_PYPROJECT = """
[tool.pytest.ini_options]
markers = ["enclosing: the enclosing project's marker"]
"""
# The inner test: it passes wherever it runs
PASSES = """
def test_passes():
    pass
"""
# The inner test, marked with a marker only the project's own configuration declares: under
# --strict-markers it runs only where that configuration was read
MARKED_BY_THE_PROJECTS_OWN_CONFIG = """
import pytest


@pytest.mark.own
def test_marked():
    pass
"""

# The inner test: pytest-randomly is not active in its run
NOT_SHUFFLED = """
def test_pytest_randomly_is_off(request):
    assert not request.config.pluginmanager.has_plugin('randomly')
"""


def test_an_in_process_inner_run_is_not_shuffled(pytester: pytest.Pytester) -> None:
    """The inner run's own plugins: pytest-randomly blocked."""
    pytester.makepyfile(test_inner=NOT_SHUFFLED)

    result = pytester.runpytest_inprocess('-p', 'no:cacheprovider')

    result.assert_outcomes(passed=1)
    assert not [line for line in result.outlines if 'randomly-seed' in line]


def test_a_subprocess_inner_run_is_not_shuffled(pytester: pytest.Pytester) -> None:
    """A subprocess reads PYTEST_ADDOPTS from its environment too."""
    pytester.makepyfile(test_inner=NOT_SHUFFLED)

    result = pytester.runpytest_subprocess('-p', 'no:cacheprovider')

    result.assert_outcomes(passed=1)
    assert not [line for line in result.outlines if 'randomly-seed' in line]


def header_value(lines: list[str], *, name: str) -> str | None:
    """Return a value from pytest's session header (``rootdir: X``, ``configfile: Y``), if shown.

    pytest prints each on a line of its own, or both on one line (``rootdir: X, configfile: Y``).

    Returns:
        The value named ``name``, or None when the header doesn't have it.

    """
    for line in lines:
        for part in line.split(', '):
            key, separator, value = part.partition(': ')
            if separator and key == name:
                return value
    return None


def config_file_read(lines: list[str]) -> str | None:
    """Return the configuration file a run read, without pytest's note on the ones it ignored.

    pytest 9 notes, in the header only (not a Python warning), the other configuration files of
    the folder it ignored: ``pytest.ini (WARNING: ignoring pytest config in tox.ini!)``. A test
    writing its own configuration beside the harness's tox.ini gets that note, and its file wins.

    Returns:
        The file's name, or None when the header names none.

    """
    value = header_value(lines, name='configfile')
    return None if value is None else value.split(' (WARNING: ', 1)[0]


def bare_pytest_run(*, project: Path) -> list[str]:
    """Run pytest in ``project`` as a plain subprocess, without this run's PYTEST_ADDOPTS.

    Returns:
        The run's output lines.

    """
    result = run_command(
        command=[
            sys.executable,
            '-m',
            'pytest',
            '-p',
            'no:cacheprovider',
            '-p',
            'no:randomly',
        ],
        working_directory=project,
        environment={name: value for name, value in os.environ.items() if name != 'PYTEST_ADDOPTS'},
        timeout_seconds=INNER_RUN_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
    )
    return result.stdout.splitlines()


def test_a_project_inside_another_project_stops_its_configuration_search_at_itself(
    tmp_path: Path,
) -> None:
    """The enclosing project's settings stay out: the run's rootdir and configfile are its own."""
    enclosing = tmp_path / 'enclosing'
    project = enclosing / 'project'
    project.mkdir(parents=True)
    (enclosing / 'pyproject.toml').write_text(ENCLOSING_PROJECT_PYPROJECT, encoding='utf-8')
    (project / 'test_passes.py').write_text(PASSES, encoding='utf-8')
    taken_from_the_enclosing_project = bare_pytest_run(project=project)

    give_project_its_own_config(project=project)
    lines = bare_pytest_run(project=project)

    assert header_value(taken_from_the_enclosing_project, name='rootdir') == str(enclosing)
    assert header_value(lines, name='rootdir') == str(project)
    assert header_value(lines, name='configfile') == OWN_CONFIG_FILE_NAME
    assert any('1 passed' in line for line in lines), lines


def test_every_pytester_project_has_a_configuration_of_its_own(pytester: pytest.Pytester) -> None:
    """The harness gives the project its file before the test runs; the inner run reads it."""
    pytester.makepyfile(test_inner=PASSES)

    result = pytester.runpytest_subprocess('-p', 'no:cacheprovider')

    result.assert_outcomes(passed=1)
    assert header_value(result.outlines, name='rootdir') == str(pytester.path)
    assert header_value(result.outlines, name='configfile') == OWN_CONFIG_FILE_NAME


def test_a_projects_own_pytest_ini_still_wins(pytester: pytest.Pytester) -> None:
    """A pytest.ini the test writes outranks the harness's file in the same folder."""
    pytester.makefile('.ini', pytest="[pytest]\nmarkers =\n    own: the project's own marker\n")
    pytester.makepyfile(test_inner=MARKED_BY_THE_PROJECTS_OWN_CONFIG)

    result = pytester.runpytest_subprocess('-p', 'no:cacheprovider', '--strict-markers')

    assert config_file_read(result.outlines) == 'pytest.ini'
    result.assert_outcomes(passed=1)


def test_a_projects_own_pyproject_settings_still_win(pytester: pytest.Pytester) -> None:
    """A pyproject.toml with [tool.pytest.ini_options] outranks the harness's file too."""
    pytester.makepyprojecttoml(
        '[tool.pytest.ini_options]\nmarkers = ["own: the project\'s own marker"]\n'
    )
    pytester.makepyfile(test_inner=MARKED_BY_THE_PROJECTS_OWN_CONFIG)

    result = pytester.runpytest_subprocess('-p', 'no:cacheprovider', '--strict-markers')

    assert config_file_read(result.outlines) == 'pyproject.toml'
    result.assert_outcomes(passed=1)


def test_an_inner_run_writes_no_junit_report(pytester):
    """The outer run's --junitxml (pyproject.toml's addopts) never reaches an inner run.

    CircleCI reads test-results/junit.xml for its test results and the split's timings; an inner
    run writing it would replace the job's report. The project's own configuration and
    pytester's removal of PYTEST_ADDOPTS keep the option out: pinned here. (#286's job 5096 log
    showed the outer run's own "generated xml file" line right after a failed inner run's
    output; it was not the inner run's.)
    """
    pytester.makepyfile(
        test_inner="""
        def test_no_report(pytestconfig):
            assert pytestconfig.option.xmlpath is None
        """
    )

    result = pytester.runpytest_inprocess()

    result.assert_outcomes(passed=1)
    assert 'generated xml file' not in result.stdout.str()
