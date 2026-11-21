"""Tests for glitchygames.checks: required() returns what is there and names what is missing."""

from __future__ import annotations

import pytest

from glitchygames.checks import MissingValueError, required


@pytest.mark.parametrize('value', [0, 0.0, '', False, [], {}, (), b''])
def test_a_falsy_value_that_is_not_none_is_returned_as_it_is(value: object):
    """Only None is missing: zero, empty and False are values the code may rely on."""
    assert required(value, what='the value') is value


def test_the_same_object_is_returned_not_a_copy():
    """The caller gets its own object back, so changes through it are seen everywhere."""
    surface_like = {'width': 640}

    returned = required(surface_like, what='the screen')

    assert returned is surface_like


def test_none_raises_a_missing_value_error_naming_what_was_missing():
    """The message is '<what> is missing', so the log says which value broke the rule."""
    with pytest.raises(MissingValueError) as raised:
        required(None, what="the scene manager's game engine")

    assert str(raised.value) == "the scene manager's game engine is missing"


def test_a_missing_value_is_a_runtime_error():
    """A missing value is a bug in the code: a RuntimeError, never a ValueError about input."""
    assert issubclass(MissingValueError, RuntimeError)
    assert not issubclass(MissingValueError, ValueError)
