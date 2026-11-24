"""The test helper that cuts writes short (tests/interrupted_writes.py) ends with its block.

Its patch must not outlive the code it cuts short: a test that fails inside the block still has
teardown writes to make (the harness's failure records, glitchygames/testing/frame_fingerprints.py),
and a patch still live then cut them short too, and its KeyboardInterrupt aborted the whole run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.interrupted_writes import cut_writes_short

# The inner run's arguments: the test-order plugin off, plain asserts, no outer options
INNER_RUN_ARGUMENTS = ('-p', 'no:randomly', '--assert=plain')

INNER_TESTS = '''
from pathlib import Path

import pytest

from tests.interrupted_writes import cut_writes_short

TEARDOWN_TEXT = 'written whole at teardown\\n'


@pytest.fixture
def teardown_write(mocker):
    """Write a file at teardown, after the test, as the harness's failure records do.

    It asks for mocker, so it is torn down before mocker's own patches are undone.
    """
    yield
    # The inner run's working directory is the outer test's pytester folder
    path = Path.cwd() / 'teardown.txt'
    path.write_text(TEARDOWN_TEXT, encoding='utf-8')


def test_fails_inside_the_block(mocker, tmp_path, teardown_write):
    with cut_writes_short(mocker=mocker, characters=2):
        (tmp_path / 'record.txt').write_text('ok', encoding='utf-8')
        raise AssertionError('the test failed inside the block')
'''


def test_the_patch_ends_with_the_block_even_when_the_write_is_cut(mocker, tmp_path):
    """A write after the block is whole: the cut stopped with the block's KeyboardInterrupt."""
    path = tmp_path / 'record.txt'

    with pytest.raises(KeyboardInterrupt), cut_writes_short(mocker=mocker, characters=1):
        path.write_text('cut', encoding='utf-8')
    path.write_text('whole', encoding='utf-8')

    assert path.read_text(encoding='utf-8') == 'whole'


def test_inside_the_block_a_write_keeps_only_its_first_characters(mocker, tmp_path):
    """What a stopped write had written stays on disk, as after a real stop."""
    path = tmp_path / 'record.txt'

    with pytest.raises(KeyboardInterrupt), cut_writes_short(mocker=mocker, characters=3):
        path.write_text('abcdef', encoding='utf-8')

    assert path.read_text(encoding='utf-8') == 'abc'


def test_reading_inside_the_block_is_untouched(mocker, tmp_path):
    """Only files opened for writing are cut short."""
    path = tmp_path / 'record.txt'
    path.write_text('abcdef', encoding='utf-8')

    with cut_writes_short(mocker=mocker, characters=1):
        text = path.read_text(encoding='utf-8')

    assert text == 'abcdef'


def test_a_test_failing_inside_the_block_keeps_its_teardown_writes(pytester):
    """The inner test fails as itself, and its teardown write is whole: the run is not aborted."""
    pytester.makepyfile(test_inner=INNER_TESTS)

    result = pytester.runpytest_inprocess(*INNER_RUN_ARGUMENTS)

    result.assert_outcomes(failed=1)
    assert 'KeyboardInterrupt' not in result.stdout.str()
    teardown = Path(pytester.path) / 'teardown.txt'
    assert teardown.read_text(encoding='utf-8') == 'written whole at teardown\n'
