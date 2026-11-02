"""Inner pytest runs (pytester) keep their tests' written order (tests/harness.py).

pytest-randomly is blocked by the project's addopts, which an inner run does not read: it was
on in every inner run, shuffling their tests with a new seed each time, so what they left
behind (frames, state) changed from run to run (BUGS.md #255; #252's memory guard tests). The
harness blocks it for every test that uses ``pytester`` (``inner_runs_keep_their_order``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

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
