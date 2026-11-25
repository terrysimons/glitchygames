"""A test that leaves faulthandler off fails, and the next has it (tests/faulthandler_guard.py)."""

import faulthandler
import sys

import pytest

from tests.faulthandler_guard import LEFT_OFF, faulthandler_left_on


class LeakingTestError(RuntimeError):
    """Raised by a test that turned faulthandler off first."""


def turn_it_off_and_raise() -> None:
    """Turn faulthandler off inside the guard, then raise.

    Raises:
        LeakingTestError: Always, with faulthandler off.

    """
    with faulthandler_left_on():
        faulthandler.disable()
        raise LeakingTestError


@pytest.fixture
def faulthandler_as_before():
    """Put faulthandler back as it was, on the process's stderr, whatever the test does."""
    was_on = faulthandler.is_enabled()
    yield
    if was_on:
        faulthandler.enable(file=sys.__stderr__)
    else:
        faulthandler.disable()


def test_a_test_that_leaves_faulthandler_off_fails_and_it_is_on_again(faulthandler_as_before):
    """The test is told why; the next test on the worker has faulthandler."""
    del faulthandler_as_before
    faulthandler.enable(file=sys.__stderr__)

    with pytest.raises(pytest.fail.Exception) as failure, faulthandler_left_on():
        faulthandler.disable()

    assert str(failure.value) == LEFT_OFF
    assert faulthandler.is_enabled()


def test_a_test_that_leaves_faulthandler_on_passes(faulthandler_as_before):
    """Turning it off and on again inside the test is the test's own business."""
    del faulthandler_as_before
    faulthandler.enable(file=sys.__stderr__)

    with faulthandler_left_on():
        faulthandler.disable()
        faulthandler.enable(file=sys.__stderr__)

    assert faulthandler.is_enabled()


def test_faulthandler_off_before_the_test_stays_off(faulthandler_as_before):
    """A run without faulthandler (``-p no:faulthandler``) is not failed, nor given it."""
    del faulthandler_as_before
    faulthandler.disable()

    with faulthandler_left_on():
        pass

    assert not faulthandler.is_enabled()


def test_a_fake_of_faulthandler_still_in_place_is_not_a_leak(faulthandler_as_before, mocker):
    """The process's own state is read, not what a test's fake answers."""
    del faulthandler_as_before
    faulthandler.enable(file=sys.__stderr__)

    with faulthandler_left_on():
        mocker.patch.object(faulthandler, 'is_enabled', return_value=False)
        enable = mocker.patch.object(faulthandler, 'enable')
    mocker.stopall()

    enable.assert_not_called()
    assert faulthandler.is_enabled()


def test_an_error_inside_is_raised_with_faulthandler_on_again(faulthandler_as_before):
    """The error is what is told; faulthandler is back for the next test all the same."""
    del faulthandler_as_before
    faulthandler.enable(file=sys.__stderr__)

    with pytest.raises(LeakingTestError):
        turn_it_off_and_raise()

    assert faulthandler.is_enabled()


def test_a_process_without_stderr_still_fails_the_test(faulthandler_as_before, mocker):
    """There is nowhere to write a traceback, so faulthandler stays off; the failure is told."""
    del faulthandler_as_before
    faulthandler.enable(file=sys.__stderr__)
    mocker.patch.object(sys, '__stderr__', None)

    with (
        pytest.raises(pytest.fail.Exception, match='left faulthandler off'),
        faulthandler_left_on(),
    ):
        faulthandler.disable()
    mocker.stopall()

    assert not faulthandler.is_enabled()


# A test that leaves faulthandler off, one after it, and the harness's fixture around both
INNER_CONFTEST = """
import pytest

from tests.faulthandler_guard import faulthandler_left_on


@pytest.fixture(autouse=True)
def faulthandler_stays_on():
    with faulthandler_left_on():
        yield
"""
INNER_TESTS = """
import faulthandler


def test_leaves_it_off():
    faulthandler.disable()


def test_after_it():
    assert faulthandler.is_enabled()
"""


def test_the_leaking_test_is_the_one_named(pytester):
    """The error is the leaking test's; the test after it finds faulthandler on."""
    pytester.makeconftest(INNER_CONFTEST)
    pytester.makepyfile(test_inner=INNER_TESTS)

    result = pytester.runpytest_inprocess()

    result.assert_outcomes(passed=2, errors=1)
    result.stdout.fnmatch_lines(['*ERROR*test_leaves_it_off*'])
