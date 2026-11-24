"""tests/original_standard_error.py: a line written to it reaches the run's own standard error."""

from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path

import pytest

from glitchygames.process import OutputCapture, run_command
from tests.original_standard_error import original_standard_error

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INNER_RUN_TIMEOUT_SECONDS = 120.0
LINE = 'written past the capture'
# A passing test that writes LINE to the run's original standard error: a line that lands in
# its captured output is never shown, as the test passes
TEST_WRITING_PAST_THE_CAPTURE = textwrap.dedent(
    f"""
    import os

    from tests.original_standard_error import original_standard_error


    def test_writes_past_the_capture(pytestconfig):
        descriptor = original_standard_error(config=pytestconfig)
        try:
            os.write(descriptor, b'{LINE}\\n')
        finally:
            os.close(descriptor)
    """
)


def test_the_original_standard_error_is_a_new_descriptor(pytestconfig):
    """A duplicate of the run's original standard error (pytest's saved one when capturing)."""
    descriptor = original_standard_error(config=pytestconfig)
    try:
        assert descriptor > 2
        os.fstat(descriptor)
    finally:
        os.close(descriptor)


@pytest.mark.parametrize(
    'capture_option',
    ['--capture=fd', '--capture=sys', '-s'],
    ids=['descriptors captured', 'streams captured', 'not captured'],
)
def test_a_line_written_during_a_test_reaches_the_runs_standard_error(tmp_path, capture_option):
    """Whatever pytest captures, the line is on the run's standard error, not in the capture.

    With descriptors captured (pytest's default) descriptor 2 is the test's capture file, so the
    saved original is the one; otherwise descriptor 2 is still the original.
    """
    (tmp_path / 'pytest.ini').write_text('[pytest]\n', encoding='utf-8')
    test_file = tmp_path / 'test_writer.py'
    test_file.write_text(TEST_WRITING_PAST_THE_CAPTURE, encoding='utf-8')
    environment = {name: value for name, value in os.environ.items() if name != 'PYTEST_ADDOPTS'}

    finished = run_command(
        command=[
            sys.executable,
            '-m',
            'pytest',
            '-c',
            str(tmp_path / 'pytest.ini'),
            '--rootdir',
            str(tmp_path),
            '-p',
            'no:cacheprovider',
            '-p',
            'no:randomly',
            capture_option,
            str(test_file),
        ],
        environment=environment,
        working_directory=PROJECT_ROOT,
        capture_output=OutputCapture.APART,
        timeout_seconds=INNER_RUN_TIMEOUT_SECONDS,
    )

    assert finished.returncode == 0, finished.stdout
    assert LINE in finished.stderr.splitlines(), (finished.stdout, finished.stderr)
